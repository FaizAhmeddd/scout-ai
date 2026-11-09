from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.engine.domain import keypoints as kp


@dataclass(slots=True)
class VideoInfo:
    path: Path
    fps: float
    width: int
    height: int
    frame_count: int
    frame_stride: int = 1

    @property
    def effective_fps(self) -> float:
        return self.fps / self.frame_stride

    def frame_to_seconds(self, frame_idx: int) -> float:
        return frame_idx / self.fps

    def seconds_to_frame(self, seconds: float) -> int:
        return int(round(seconds * self.fps))


@dataclass(slots=True)
class PlayerObservation:
    frame_idx: int
    track_id: int
    bbox: np.ndarray  # (4,) xyxy
    keypoints: np.ndarray  # (17, 3) x, y, confidence
    confidence: float
    torso_color_lab: np.ndarray | None = None  # (3,) median shirt colour in CIE Lab (display)
    torso_hist: np.ndarray | None = None  # shirt colour histogram (team clustering, identity matching)
    on_grass: bool = True  # feet stand on pitch grass (False for coaches, stewards, crowd)
    isolated: bool = False  # box does not overlap another person (clean crop)
    reid_embedding: np.ndarray | None = None  # L2-normalised appearance embedding (sampled frames only)
    role: str = "player"  # ROLE_PLAYER / ROLE_GOALKEEPER / ROLE_REFEREE as seen by the football detector
    thumbnail: np.ndarray | None = None  # crop kept only for a track's few largest, clearest frames

    def keypoint(self, index: int, min_conf: float) -> np.ndarray | None:
        x, y, c = self.keypoints[index]
        return np.array([x, y], dtype=np.float32) if c >= min_conf else None

    def foot_point(self, min_conf: float = 0.0) -> np.ndarray:
        """Ground position: bottom-centre of the box.

        Deliberately not the ankle keypoints: ankles flicker in and out of confidence frame to frame,
        and switching between sources would show up as fake speed spikes.
        """
        return np.array([(self.bbox[0] + self.bbox[2]) / 2, self.bbox[3]], dtype=np.float32)

    def feet(self, min_conf: float) -> list[np.ndarray]:
        """Ankle keypoints when visible (used for ball control), else the ground point."""
        ankles = [
            a
            for a in (self.keypoint(kp.LEFT_ANKLE, min_conf), self.keypoint(kp.RIGHT_ANKLE, min_conf))
            if a is not None
        ]
        return ankles or [self.foot_point()]

    def body_height_px(self, min_conf: float) -> float:
        """Standing height in pixels estimated from nose-to-ankle span, falling back to box height."""
        nose = self.keypoint(kp.NOSE, min_conf)
        ankles = [
            a
            for a in (self.keypoint(kp.LEFT_ANKLE, min_conf), self.keypoint(kp.RIGHT_ANKLE, min_conf))
            if a is not None
        ]
        if nose is not None and ankles:
            span = max(a[1] for a in ankles) - nose[1]
            if span > 0.5 * self.box_height:
                return float(span / kp.NOSE_TO_ANKLE_HEIGHT_RATIO)
        return float(self.box_height)

    @property
    def box_height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])

    @property
    def center(self) -> np.ndarray:
        return np.array([(self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2], dtype=np.float32)


@dataclass(slots=True)
class BallObservation:
    frame_idx: int
    center: np.ndarray  # (2,)
    confidence: float
    interpolated: bool = False


@dataclass(slots=True)
class CameraMotion:
    """Per-frame 3x3 transforms mapping each frame's pixels into the reference (first processed) frame."""

    to_reference: dict[int, np.ndarray] = field(default_factory=dict)
    scene_cuts: set[int] = field(default_factory=set)

    def transform(self, frame_idx: int) -> np.ndarray:
        return self.to_reference.get(frame_idx, np.eye(3, dtype=np.float64))

    def stabilize(self, frame_idx: int, point: np.ndarray) -> np.ndarray:
        m = self.transform(frame_idx)
        vec = m @ np.array([point[0], point[1], 1.0])
        return (vec[:2] / vec[2]).astype(np.float32)

    def destabilize(self, frame_idx: int, point: np.ndarray) -> np.ndarray:
        m = np.linalg.inv(self.transform(frame_idx))
        vec = m @ np.array([point[0], point[1], 1.0])
        return (vec[:2] / vec[2]).astype(np.float32)

    def scale(self, frame_idx: int) -> float:
        """Isotropic scale of the frame->reference transform (zoom compensation)."""
        m = self.transform(frame_idx)
        return float(np.sqrt(abs(np.linalg.det(m[:2, :2]))))

    def segment_id(self, frame_idx: int) -> int:
        """Index of the continuous shot a frame belongs to (incremented at every scene cut)."""
        return sum(1 for cut in self.scene_cuts if cut <= frame_idx)


@dataclass
class TrackingResult:
    """Output of pass 1 — everything needed for analysis without re-reading the video."""

    video: VideoInfo
    processed_frames: list[int]
    tracks: dict[int, list[PlayerObservation]]
    balls: dict[int, BallObservation]
    camera: CameraMotion
    pitch_homographies: dict[int, np.ndarray] = field(default_factory=dict)  # frame -> image->pitch (metres)


@dataclass
class TeamAssignment:
    team_of_track: dict[int, int]  # raw track id -> team id (OTHER_TEAM for referees / unknown)
    colors_bgr: dict[int, tuple[int, int, int]]
    color_names: dict[int, str]
    centers_lab: dict[int, np.ndarray]


OTHER_TEAM = -1

ROLE_PLAYER = "player"
ROLE_GOALKEEPER = "goalkeeper"
ROLE_REFEREE = "referee"


def track_role(observations: list[PlayerObservation]) -> str:
    """Majority role over a track (single-frame role labels flicker, e.g. a player briefly seen as referee)."""
    counts: dict[str, int] = {}
    for obs in observations:
        counts[obs.role] = counts.get(obs.role, 0) + 1
    return max(counts, key=counts.get) if counts else ROLE_PLAYER


@dataclass
class PlayerTrack:
    """A player after ID-switch repair: one identity, possibly built from several tracker fragments."""

    player_id: int
    team_id: int
    source_track_ids: list[int]
    observations: list[PlayerObservation]
    thumbnail: np.ndarray | None

    @property
    def first_frame(self) -> int:
        return self.observations[0].frame_idx

    @property
    def last_frame(self) -> int:
        return self.observations[-1].frame_idx

    def by_frame(self) -> dict[int, PlayerObservation]:
        return {obs.frame_idx: obs for obs in self.observations}


@dataclass
class AnalysisTarget:
    team_id: int
    player_id: int | None = None
    jersey_number: int | None = None
    label: str = ""

    @property
    def is_player_mode(self) -> bool:
        return self.player_id is not None
