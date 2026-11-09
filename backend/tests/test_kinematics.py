import numpy as np
import pytest

from app.core.app_config import KinematicsConfig
from app.engine.metrics.kinematics import KinematicsAnalyzer
from tests.factories import kinematics_for, series_from_speeds


def test_constant_running_speed_gives_expected_distance_and_zone():
    profile = kinematics_for([18.0] * 250)  # 10 s at 18 km/h = 5 m/s

    assert profile.total_distance_m == pytest.approx(50.0, rel=0.02)
    assert profile.top_speed_kmh == pytest.approx(18.0, rel=0.02)
    assert profile.distance_by_zone_m["running"] == pytest.approx(50.0, rel=0.02)
    assert profile.sprints == []


def _ramp(start: float, end: float, frames: int = 25) -> list[float]:
    """Physically plausible change of speed over one second."""
    return list(np.linspace(start, end, frames))


def test_sprint_detected_only_when_long_enough():
    short_burst = kinematics_for([10.0] * 50 + _ramp(10, 30, 8) + [30.0] * 4 + _ramp(30, 10, 8) + [10.0] * 50)
    real_sprint = kinematics_for([10.0] * 50 + _ramp(10, 30) + [30.0] * 50 + _ramp(30, 10) + [10.0] * 50)

    assert len(short_burst.sprints) == 0
    assert len(real_sprint.sprints) == 1
    assert real_sprint.sprints[0].peak_kmh == pytest.approx(30.0, rel=0.05)
    assert real_sprint.top_speed_kmh == pytest.approx(30.0, rel=0.05)


def test_single_frame_spike_does_not_set_top_speed():
    profile = kinematics_for([8.0] * 100 + [30.0] + [8.0] * 100)
    assert profile.top_speed_kmh < 12.0


def test_impossible_speeds_are_discarded():
    profile = kinematics_for([10.0] * 50 + [80.0] * 3 + [10.0] * 50)
    assert profile.top_speed_kmh < 38.0


def test_identity_swap_teleport_adds_no_distance():
    series = series_from_speeds([10.0] * 100)
    series.xy_m[50:] += [15.0, 0.0]  # tracker jumps to a team-mate 15 m away
    profile = KinematicsAnalyzer(KinematicsConfig()).analyze(series)

    assert profile.total_distance_m == pytest.approx(10 / 3.6 * 4, rel=0.1)  # ~11 m from real running only
    assert profile.top_speed_kmh < 12.0


def test_distance_until_is_monotonic():
    profile = kinematics_for([20.0] * 100)
    assert profile.distance_until(1.0) < profile.distance_until(2.0) < profile.distance_until(4.0)
