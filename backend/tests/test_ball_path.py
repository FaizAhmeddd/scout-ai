import numpy as np

from app.engine.domain.models import BallObservation
from app.engine.metrics.ball_path import build_ball_path
from app.engine.metrics.possession import PossessionTimeline


class _Transformer:
    def __init__(self, calibrated: bool):
        self.uses_pitch_coordinates = calibrated

    def project(self, frame_idx, point):
        return None if frame_idx == 2 else np.asarray(point, dtype=float)  # frame 2 is uncalibrated


def _balls(positions: dict[int, tuple[float, float]]):
    return {f: BallObservation(frame_idx=f, center=np.array(p, dtype=np.float32), confidence=0.9) for f, p in positions.items()}


def test_ball_path_keeps_calibrated_on_pitch_points_with_the_controlling_team():
    possession = PossessionTimeline(frame_seconds=0.04, team_by_frame={0: 1, 1: 1, 3: 0})
    balls = _balls({0: (10, 10), 1: (12, 11), 2: (14, 12), 3: (16, 12), 4: (500, 500)})  # 2 uncalibrated, 4 off the pitch

    path = build_ball_path(balls, _Transformer(True), possession, {0: (0, 0, 255), 1: (255, 0, 0)}, 25.0, 105.0, 68.0)

    assert list(path.frames) == [0, 1, 3]
    assert path.team_at_point == [1, 1, 0]


def test_ball_path_is_absent_without_pitch_calibration_or_enough_points():
    possession = PossessionTimeline(frame_seconds=0.04)
    assert build_ball_path(_balls({0: (1, 1), 1: (2, 2)}), _Transformer(False), possession, {}, 25.0, 105.0, 68.0) is None
    assert build_ball_path(_balls({0: (1, 1)}), _Transformer(True), possession, {}, 25.0, 105.0, 68.0) is None
