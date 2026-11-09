from dataclasses import dataclass

import numpy as np

from app.core.app_config import PoseMetricsConfig
from app.engine.domain import keypoints as kp
from app.engine.domain.models import PlayerTrack
from app.engine.metrics.kinematics import KinematicProfile

_MIN_CADENCE_WINDOW_S = 1.0
_MIN_PLAUSIBLE_CADENCE = 90.0
_MAX_PLAUSIBLE_CADENCE = 260.0


@dataclass
class PoseProfile:
    cadence_spm: float | None  # running steps per minute
    trunk_lean_deg: float | None  # forward/side lean of the torso while running
    keypoint_visibility: float  # share of keypoints confidently detected


class PoseMetricsAnalyzer:
    """Biomechanics that only a pose model can provide: running cadence and trunk lean."""

    def __init__(self, config: PoseMetricsConfig, min_keypoint_conf: float):
        self.config = config
        self.min_keypoint_conf = min_keypoint_conf

    def analyze(self, player: PlayerTrack, kinematics: KinematicProfile, fps: float) -> PoseProfile:
        speed_by_frame = {
            int(round(s * fps)): v for s, v in zip(kinematics.seconds, kinematics.speed_kmh) if not np.isnan(v)
        }
        running = [
            o for o in player.observations
            if speed_by_frame.get(o.frame_idx, 0.0) >= self.config.min_speed_kmh_for_cadence
        ]
        visibility = float(
            np.mean([(o.keypoints[:, 2] >= self.min_keypoint_conf).mean() for o in player.observations])
        ) if player.observations else 0.0
        return PoseProfile(
            cadence_spm=self._cadence(running, fps),
            trunk_lean_deg=self._trunk_lean(running),
            keypoint_visibility=visibility,
        )

    def _cadence(self, running, fps: float) -> float | None:
        """Counts left/right ankle crossings (each crossing is one step) over continuous running stretches."""
        total_steps, total_time = 0, 0.0
        for chunk in _contiguous(running, max_frame_gap=max(3, round(0.25 * fps))):
            signal, times = [], []
            for obs in chunk:
                left = obs.keypoint(kp.LEFT_ANKLE, self.min_keypoint_conf)
                right = obs.keypoint(kp.RIGHT_ANKLE, self.min_keypoint_conf)
                if left is None or right is None:
                    continue
                signal.append((left[1] - right[1]) / max(obs.body_height_px(self.min_keypoint_conf), 1.0))
                times.append(obs.frame_idx / fps)
            if len(signal) < 4 or times[-1] - times[0] < _MIN_CADENCE_WINDOW_S:
                continue
            centered = np.array(signal) - np.median(signal)
            crossings = int(np.sum(np.diff(np.sign(centered)) != 0))
            total_steps += crossings
            total_time += times[-1] - times[0]
        if total_time < _MIN_CADENCE_WINDOW_S:
            return None
        cadence = total_steps / total_time * 60
        return float(cadence) if _MIN_PLAUSIBLE_CADENCE <= cadence <= _MAX_PLAUSIBLE_CADENCE else None

    def _trunk_lean(self, running) -> float | None:
        angles = []
        for obs in running:
            points = [obs.keypoint(i, self.min_keypoint_conf) for i in kp.TORSO_POLYGON]
            if any(p is None for p in points):
                continue
            shoulders = (points[0] + points[1]) / 2
            hips = (points[2] + points[3]) / 2
            dx, dy = shoulders - hips
            if dy >= 0:
                continue
            angles.append(np.degrees(np.arctan2(abs(dx), -dy)))
        return float(np.median(angles)) if angles else None


def _contiguous(observations, max_frame_gap: int):
    chunk = []
    for obs in observations:
        if chunk and obs.frame_idx - chunk[-1].frame_idx > max_frame_gap:
            yield chunk
            chunk = []
        chunk.append(obs)
    if chunk:
        yield chunk
