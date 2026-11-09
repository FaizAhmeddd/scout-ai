import logging
from dataclasses import dataclass

import cv2
import numpy as np
import pandas as pd

from app.core.app_config import GeometryConfig, PitchConfig
from app.engine.domain.models import CameraMotion, PlayerObservation, PlayerTrack, VideoInfo

logger = logging.getLogger(__name__)

_HEIGHT_SMOOTHING_OBS = 25
_PLAUSIBLE_METRES_PER_PX = (0.002, 0.5)
_OFF_PITCH_MARGIN_M = 5.0


@dataclass
class PositionSeries:
    """A player's trajectory in metres. Positions are continuous within a run; runs break at gaps and cuts."""

    frames: np.ndarray
    seconds: np.ndarray
    xy_m: np.ndarray
    run_ids: np.ndarray
    on_pitch: bool

    def __len__(self) -> int:
        return len(self.frames)

    def runs(self) -> list[np.ndarray]:
        return [np.flatnonzero(self.run_ids == r) for r in np.unique(self.run_ids)]

    def position_at(self, frame_idx: int, max_frame_gap: int) -> np.ndarray | None:
        if not len(self.frames):
            return None
        i = int(np.argmin(np.abs(self.frames - frame_idx)))
        return self.xy_m[i] if abs(int(self.frames[i]) - frame_idx) <= max_frame_gap else None


class ViewTransformer:
    """Converts player positions into metres, choosing the most accurate geometry available.

    1. homography      - manual 4+ point calibration on the first frame (first camera shot only).
    2. pitch_keypoints - automatic per-frame calibration from detected pitch landmarks (real pitch metres).
    3. pose_scale      - no calibration: each player's pose-estimated height (~1.75 m) is a local ruler,
                         so displacements are measured in metres at the player's own depth.
    """

    def __init__(
        self,
        config: GeometryConfig,
        camera: CameraMotion,
        video: VideoInfo,
        min_keypoint_conf: float,
        max_gap_seconds: float,
        pitch_homographies: dict[int, np.ndarray] | None = None,
        processed_frames: list[int] | None = None,
        pitch_config: PitchConfig | None = None,
    ):
        self.config = config
        self.camera = camera
        self.video = video
        self.min_keypoint_conf = min_keypoint_conf
        self.max_gap_seconds = max_gap_seconds
        self.homography = self._build_manual_homography()
        self.frame_homographies: dict[int, np.ndarray] = {}
        if self.homography is None and config.mode in ("auto", "pitch_keypoints"):
            self.frame_homographies = self._build_frame_homographies(
                pitch_homographies or {}, processed_frames or [], pitch_config or PitchConfig()
            )
        self._segment_scale: dict[int, float] = {}
        logger.info("Geometry mode: %s", self.mode)

    @property
    def mode(self) -> str:
        if self.homography is not None:
            return "homography"
        return "pitch_keypoints" if self.frame_homographies else "pose_scale"

    @property
    def uses_pitch_coordinates(self) -> bool:
        return self.mode != "pose_scale"

    def project(self, frame_idx: int, image_point: np.ndarray) -> np.ndarray | None:
        """Pitch coordinates (metres) of an image point, when the frame is calibrated."""
        homography, point = self._homography_for(frame_idx, image_point)
        if homography is None:
            return None
        return cv2.perspectiveTransform(point.astype(np.float64).reshape(1, 1, 2), homography).reshape(2)

    def fit(self, players: list[PlayerTrack]) -> None:
        """Learns a typical metres-per-pixel per camera shot, used to anchor pose-scale positions."""
        per_segment: dict[int, list[float]] = {}
        for player in players:
            for obs in player.observations:
                mpp = self._metres_per_px(obs.frame_idx, obs.body_height_px(self.min_keypoint_conf))
                if mpp is not None:
                    per_segment.setdefault(self.camera.segment_id(obs.frame_idx), []).append(mpp)
        self._segment_scale = {seg: float(np.median(v)) for seg, v in per_segment.items()}

    def series(self, player: PlayerTrack) -> PositionSeries:
        if self.mode == "pose_scale":
            return self._pose_scale_series(player.observations)
        return self._pitch_series(player.observations)

    # ------------------------------------------------------------------ pitch coordinates

    def _pitch_series(self, observations: list[PlayerObservation]) -> PositionSeries:
        frames, points = [], []
        for obs in observations:
            xy = self.project(obs.frame_idx, obs.foot_point(self.min_keypoint_conf))
            if xy is not None and self._on_pitch(xy):
                frames.append(obs.frame_idx)
                points.append(xy)
        if not frames:
            return self._empty(on_pitch=True)
        frames_arr = np.array(frames)
        seconds = frames_arr / self.video.fps
        segments = np.array([self.camera.segment_id(f) for f in frames])
        return PositionSeries(frames_arr, seconds, np.stack(points), self._run_ids(seconds, segments), on_pitch=True)

    def _homography_for(self, frame_idx: int, image_point: np.ndarray) -> tuple[np.ndarray | None, np.ndarray]:
        if self.homography is not None:
            if self.camera.segment_id(frame_idx) != 0:
                return None, image_point
            return self.homography, self.camera.stabilize(frame_idx, image_point)
        return self.frame_homographies.get(frame_idx), image_point

    def _on_pitch(self, xy: np.ndarray) -> bool:
        m = _OFF_PITCH_MARGIN_M
        return -m <= xy[0] <= self.config.pitch_length_m + m and -m <= xy[1] <= self.config.pitch_width_m + m

    def _build_frame_homographies(
        self, detected: dict[int, np.ndarray], processed_frames: list[int], pitch: PitchConfig
    ) -> dict[int, np.ndarray]:
        attempted = max(len(processed_frames) / pitch.every_n_frames, 1)
        coverage = len(detected) / attempted
        if coverage < pitch.min_coverage:
            if detected:
                logger.warning("Pitch calibrated in only %.0f%% of frames - using pose-scale geometry", coverage * 100)
            return {}

        keys = sorted(detected)
        normalized = np.stack([detected[k] / detected[k][2, 2] for k in keys])
        segments = np.array([self.camera.segment_id(k) for k in keys])
        half = pitch.smoothing_window // 2
        smoothed = {}
        for i, key in enumerate(keys):
            lo, hi = max(i - half, 0), min(i + half + 1, len(keys))
            same_shot = segments[lo:hi] == segments[i]
            smoothed[key] = np.median(normalized[lo:hi][same_shot], axis=0)

        max_gap = pitch.every_n_frames * self.video.frame_stride * 2
        result = {}
        for frame_idx in processed_frames:
            j = int(np.searchsorted(keys, frame_idx))
            nearest = min(
                (keys[c] for c in (j - 1, j) if 0 <= c < len(keys)),
                key=lambda k: abs(k - frame_idx),
                default=None,
            )
            if (
                nearest is not None
                and abs(nearest - frame_idx) <= max_gap
                and self.camera.segment_id(nearest) == self.camera.segment_id(frame_idx)
            ):
                result[frame_idx] = smoothed[nearest]
        logger.info("Automatic pitch calibration covers %d/%d frames", len(result), len(processed_frames))
        return result

    def _build_manual_homography(self) -> np.ndarray | None:
        calibration = self.config.calibration
        if self.config.mode in ("pose_scale", "pitch_keypoints") or not calibration.is_set:
            if self.config.mode == "homography":
                raise ValueError("geometry.mode is 'homography' but no calibration points are configured")
            return None
        image_pts = np.array(calibration.image_points, dtype=np.float32)
        pitch_pts = np.array(calibration.pitch_points, dtype=np.float32)
        homography, _ = cv2.findHomography(image_pts, pitch_pts, cv2.RANSAC if len(image_pts) > 4 else 0)
        if homography is None:
            raise ValueError("Could not compute a homography from the calibration points")
        logger.info("Using manual pitch homography from %d calibration points", len(image_pts))
        return homography

    # ------------------------------------------------------------------ pose scale

    def _pose_scale_series(self, observations: list[PlayerObservation]) -> PositionSeries:
        if not observations:
            return self._empty(on_pitch=False)
        frames = np.array([o.frame_idx for o in observations])
        seconds = frames / self.video.fps
        stabilized = np.stack(
            [self.camera.stabilize(o.frame_idx, o.foot_point(self.min_keypoint_conf)) for o in observations]
        ).astype(np.float64)
        segments = np.array([self.camera.segment_id(f) for f in frames])
        run_ids = self._run_ids(seconds, segments)

        mpp = self._smoothed_metres_per_px(observations)
        xy = np.zeros_like(stabilized)
        for run in np.unique(run_ids):
            idx = np.flatnonzero(run_ids == run)
            anchor_scale = self._segment_scale.get(int(segments[idx[0]]), float(np.nanmedian(mpp)))
            xy[idx[0]] = stabilized[idx[0]] * anchor_scale
            steps = np.diff(stabilized[idx], axis=0) * ((mpp[idx][1:] + mpp[idx][:-1]) / 2)[:, None]
            xy[idx[1:]] = xy[idx[0]] + np.cumsum(steps, axis=0)
        return PositionSeries(frames, seconds, xy, run_ids, on_pitch=False)

    def _smoothed_metres_per_px(self, observations: list[PlayerObservation]) -> np.ndarray:
        heights = pd.Series(
            [o.body_height_px(self.min_keypoint_conf) * self.camera.scale(o.frame_idx) for o in observations]
        )
        smoothed = heights.rolling(_HEIGHT_SMOOTHING_OBS, center=True, min_periods=1).median().to_numpy()
        mpp = self.config.reference_height_m / np.maximum(smoothed, 1.0)
        return np.clip(mpp, *_PLAUSIBLE_METRES_PER_PX)

    def _metres_per_px(self, frame_idx: int, height_px: float) -> float | None:
        if height_px <= 0:
            return None
        mpp = self.config.reference_height_m / (height_px * self.camera.scale(frame_idx))
        low, high = _PLAUSIBLE_METRES_PER_PX
        return mpp if low <= mpp <= high else None

    # ------------------------------------------------------------------ shared

    def _run_ids(self, seconds: np.ndarray, segments: np.ndarray) -> np.ndarray:
        breaks = np.zeros(len(seconds), dtype=int)
        if len(seconds) > 1:
            breaks[1:] = (np.diff(seconds) > self.max_gap_seconds) | (np.diff(segments) != 0)
        return np.cumsum(breaks)

    @staticmethod
    def _empty(on_pitch: bool) -> PositionSeries:
        return PositionSeries(np.array([], int), np.array([]), np.zeros((0, 2)), np.array([], int), on_pitch)
