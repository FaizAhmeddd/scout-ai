import numpy as np

from app.core.app_config import KinematicsConfig
from app.engine.domain.models import PlayerObservation, PlayerTrack
from app.engine.geometry.view_transformer import PositionSeries
from app.engine.metrics.kinematics import KinematicsAnalyzer
from app.engine.teams.shirt_color import SHIRT_HISTOGRAM_BINS


def _hist(**bins: float) -> np.ndarray:
    index = {"black": 0, "grey": 1, "white": 2, "red": 4, "yellow": 8, "blue": 16}
    hist = np.zeros(SHIRT_HISTOGRAM_BINS, dtype=np.float32)
    for name, share in bins.items():
        hist[index[name]] = share
    return hist


# (median Lab, histogram) of realistic kits — including the hard cases for single-colour features.
KITS = {
    "white_red_band": ((92.0, 2.0, 2.0), _hist(white=0.8, red=0.2)),
    "red_white_number": ((60.0, 45.0, 30.0), _hist(red=0.6, white=0.4)),
    "red": ((45.0, 62.0, 45.0), _hist(red=1.0)),
    "blue": ((35.0, 10.0, -50.0), _hist(blue=1.0)),
    "yellow_referee": ((85.0, -10.0, 80.0), _hist(yellow=0.7, black=0.3)),
}


def appearance(seed: int, dims: int = 512) -> np.ndarray:
    """A deterministic, L2-normalised fake ReID embedding; different seeds look like different people."""
    vector = np.random.default_rng(seed).normal(size=dims).astype(np.float32)
    return (vector / np.linalg.norm(vector)).astype(np.float16)


def observation(frame_idx: int, track_id: int, foot_x: float, foot_y: float, height: float = 100.0,
                kit: str | None = "red", embedding: np.ndarray | None = None) -> PlayerObservation:
    """A standing player whose ankles touch (foot_x, foot_y) and whose nose is `height * 0.88` above."""
    keypoints = np.zeros((17, 3), dtype=np.float32)
    keypoints[0] = (foot_x, foot_y - 0.88 * height, 0.9)
    keypoints[15] = (foot_x - 5, foot_y, 0.9)
    keypoints[16] = (foot_x + 5, foot_y, 0.9)
    bbox = np.array([foot_x - 20, foot_y - height, foot_x + 20, foot_y], dtype=np.float32)
    lab, hist = KITS[kit] if kit else (None, None)
    return PlayerObservation(
        frame_idx=frame_idx,
        track_id=track_id,
        bbox=bbox,
        keypoints=keypoints,
        confidence=0.9,
        torso_color_lab=np.array(lab, dtype=np.float32) if lab else None,
        torso_hist=hist,
        reid_embedding=embedding,
    )


def series_from_speeds(speeds_kmh: list[float], fps: float = 25.0) -> PositionSeries:
    """Straight-line trajectory moving at the given per-frame speeds."""
    steps = np.array(speeds_kmh) / 3.6 / fps
    x = np.concatenate([[0.0], np.cumsum(steps)])
    frames = np.arange(len(x))
    return PositionSeries(
        frames=frames,
        seconds=frames / fps,
        xy_m=np.stack([x, np.zeros_like(x)], axis=1),
        run_ids=np.zeros(len(x), dtype=int),
        on_pitch=False,
    )


def player(player_id: int, observations: list[PlayerObservation], team_id: int = 0) -> PlayerTrack:
    return PlayerTrack(player_id=player_id, team_id=team_id, source_track_ids=[player_id], observations=observations, thumbnail=None)


def kinematics_for(speeds_kmh: list[float]):
    return KinematicsAnalyzer(KinematicsConfig()).analyze(series_from_speeds(speeds_kmh))
