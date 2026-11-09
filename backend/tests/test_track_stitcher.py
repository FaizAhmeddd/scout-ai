import numpy as np

from app.core.app_config import StitchingConfig
from app.engine.domain.models import CameraMotion, TeamAssignment
from app.engine.tracking.track_stitcher import TrackStitcher
from tests.factories import observation


def _teams(team_of_track: dict[int, int]) -> TeamAssignment:
    return TeamAssignment(team_of_track=team_of_track, colors_bgr={}, color_names={}, centers_lab={})


def _fragment(track_id: int, frames: range, x_start: float, kit: str = "red"):
    return [observation(f, track_id, x_start + 2 * (f - frames.start), 500, kit=kit) for f in frames]


def test_fragments_of_same_player_are_merged():
    tracks = {1: _fragment(1, range(0, 50), 100), 2: _fragment(2, range(60, 100), 125)}
    players = TrackStitcher(StitchingConfig(), 25.0, 0.3).stitch(tracks, _teams({1: 0, 2: 0}), CameraMotion())

    assert len(players) == 1
    assert players[0].source_track_ids == [1, 2]
    assert len(players[0].observations) == 90


def test_different_teams_or_far_positions_stay_separate():
    tracks = {
        1: _fragment(1, range(0, 50), 100),
        2: _fragment(2, range(60, 100), 125),  # close but other team
        3: _fragment(3, range(60, 100), 1500),  # same team but too far away
    }
    players = TrackStitcher(StitchingConfig(), 25.0, 0.3).stitch(tracks, _teams({1: 0, 2: 1, 3: 0}), CameraMotion())
    assert len(players) == 3


def test_shirt_colour_mismatch_blocks_merge():
    tracks = {1: _fragment(1, range(0, 50), 100), 2: _fragment(2, range(60, 100), 125, kit="blue")}
    players = TrackStitcher(StitchingConfig(), 25.0, 0.3).stitch(tracks, _teams({1: 0, 2: 0}), CameraMotion())
    assert len(players) == 2
    assert np.all([len(p.source_track_ids) == 1 for p in players])
