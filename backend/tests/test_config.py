import pytest
from pydantic import ValidationError

from app.core.app_config import AppConfig, CalibrationConfig, load_app_config


def test_default_config_file_loads():
    config = load_app_config()
    assert isinstance(config, AppConfig)
    assert config.pose.model == "yolo26n-pose.pt"
    assert config.gemini.model == "gemini-3.7-flash"
    assert config.kinematics.speed_zones_kmh["sprinting"][0] == 25


def test_calibration_requires_matching_points():
    with pytest.raises(ValidationError):
        CalibrationConfig(image_points=[[0, 0]] * 4, pitch_points=None)
    with pytest.raises(ValidationError):
        CalibrationConfig(image_points=[[0, 0]] * 3, pitch_points=[[0, 0]] * 3)
    assert CalibrationConfig(image_points=[[0, 0]] * 4, pitch_points=[[1, 1]] * 4).is_set
