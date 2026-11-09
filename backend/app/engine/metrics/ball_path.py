from dataclasses import dataclass

import numpy as np

from app.engine.domain.models import BallObservation
from app.engine.geometry.view_transformer import ViewTransformer
from app.engine.metrics.possession import PossessionTimeline
from app.engine.render.palette import BGR

_PITCH_MARGIN_M = 3.0


@dataclass
class BallPath:
    """The ball's trajectory in pitch metres, with the team that controlled it at each point (None = loose ball)."""

    frames: np.ndarray
    xy_m: np.ndarray
    team_at_point: list[int | None]
    team_colors_bgr: dict[int, BGR]
    fps: float


def build_ball_path(
    balls: dict[int, BallObservation],
    transformer: ViewTransformer,
    possession: PossessionTimeline,
    team_colors_bgr: dict[int, BGR],
    fps: float,
    pitch_length_m: float,
    pitch_width_m: float,
) -> BallPath | None:
    """Projects every tracked ball position onto the pitch; None without pitch calibration (no honest coordinates)."""
    if not transformer.uses_pitch_coordinates:
        return None
    frames, points, teams = [], [], []
    for frame_idx in sorted(balls):
        xy = transformer.project(frame_idx, balls[frame_idx].center)
        if xy is None:
            continue
        if not (-_PITCH_MARGIN_M <= xy[0] <= pitch_length_m + _PITCH_MARGIN_M
                and -_PITCH_MARGIN_M <= xy[1] <= pitch_width_m + _PITCH_MARGIN_M):
            continue
        frames.append(frame_idx)
        points.append(xy)
        teams.append(possession.team_by_frame.get(frame_idx))
    if len(frames) < 2:
        return None
    return BallPath(np.array(frames), np.stack(points), teams, team_colors_bgr, fps)
