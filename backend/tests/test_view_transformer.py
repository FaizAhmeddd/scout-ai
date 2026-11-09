import numpy as np
import pytest

from app.core.app_config import CalibrationConfig, GeometryConfig
from app.engine.domain.models import CameraMotion, VideoInfo
from app.engine.geometry.view_transformer import ViewTransformer
from tests.factories import observation, player

VIDEO = VideoInfo(path=None, fps=25.0, width=1920, height=1080, frame_count=100)


def test_homography_maps_calibration_square_to_metres():
    calibration = CalibrationConfig(
        image_points=[[100, 100], [1100, 100], [1100, 600], [100, 600]],
        pitch_points=[[0, 0], [20, 0], [20, 10], [0, 10]],
    )
    transformer = ViewTransformer(GeometryConfig(calibration=calibration), CameraMotion(), VIDEO, 0.3, 0.6)
    series = transformer.series(player(1, [observation(0, 1, 600, 350), observation(1, 1, 1100, 600)]))

    assert transformer.mode == "homography"
    assert series.on_pitch
    np.testing.assert_allclose(series.xy_m[0], [10, 5], atol=1e-3)
    np.testing.assert_allclose(series.xy_m[1], [20, 10], atol=1e-3)


def test_pose_scale_uses_player_height_as_ruler():
    # 100 px tall player == 1.75 m, so moving 100 px sideways == 1.75 m.
    transformer = ViewTransformer(GeometryConfig(), CameraMotion(), VIDEO, 0.3, 0.6)
    track = player(1, [observation(f, 1, 500 + 4 * f, 500) for f in range(26)])
    transformer.fit([track])
    series = transformer.series(track)

    assert transformer.mode == "pose_scale"
    assert not series.on_pitch
    travelled = np.linalg.norm(series.xy_m[-1] - series.xy_m[0])
    assert travelled == pytest.approx(100 * 0.0175, rel=0.02)


def test_runs_break_on_long_gaps():
    transformer = ViewTransformer(GeometryConfig(), CameraMotion(), VIDEO, 0.3, 0.6)
    track = player(1, [observation(f, 1, 500, 500) for f in list(range(10)) + list(range(60, 70))])
    transformer.fit([track])
    assert len(transformer.series(track).runs()) == 2
