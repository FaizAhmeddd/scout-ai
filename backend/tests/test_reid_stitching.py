from app.core.app_config import ReIdConfig, StitchingConfig
from app.engine.domain.models import CameraMotion, TeamAssignment
from app.engine.tracking.track_stitcher import TrackStitcher
from tests.factories import appearance, observation

FPS = 25.0


def _teams(track_ids) -> TeamAssignment:
    return TeamAssignment(team_of_track={t: 0 for t in track_ids}, colors_bgr={}, color_names={}, centers_lab={})


def _fragment(track_id: int, frames: range, x_start: float, person: int | None):
    """Same kit for everyone; only the ReID appearance (seeded per person) tells team-mates apart."""
    return [
        observation(f, track_id, x_start + 2 * (f - frames.start), 500, kit="red",
                    embedding=appearance(person) if person is not None else None)
        for f in frames
    ]


def _stitch(tracks, reid: ReIdConfig):
    return TrackStitcher(StitchingConfig(), FPS, 0.3, reid).stitch(tracks, _teams(tracks), CameraMotion())


def test_reid_keeps_same_kit_team_mates_apart():
    # Fragment 2 starts right where fragment 1 ended (a crossing), but it is a different person.
    tracks = {1: _fragment(1, range(0, 50), 100, person=7), 2: _fragment(2, range(55, 100), 200, person=8)}
    without_reid = _stitch(tracks, ReIdConfig(enabled=False))
    with_reid = _stitch(tracks, ReIdConfig())

    assert len(without_reid) == 1  # colour + position alone wrongly merge the two team-mates
    assert len(with_reid) == 2


def test_reid_relinks_a_player_after_a_long_absence():
    # Player 7 leaves the shot for 8 s (beyond the 3 s motion window) and re-enters.
    tracks = {1: _fragment(1, range(0, 50), 100, person=7), 2: _fragment(2, range(250, 300), 400, person=7)}
    players = _stitch(tracks, ReIdConfig())

    assert len(players) == 1
    assert players[0].source_track_ids == [1, 2]


def test_long_gaps_need_appearance_evidence():
    tracks = {1: _fragment(1, range(0, 50), 100, person=None), 2: _fragment(2, range(250, 300), 400, person=None)}
    assert len(_stitch(tracks, ReIdConfig())) == 2
