from types import SimpleNamespace

from app.engine.fusion.report_builder import ReportBuilder
from app.engine.metrics.possession import PossessionTimeline

_TEAM_MODE = SimpleNamespace(is_player_mode=False)


def _timeline(controlled_frames: int, total_frames: int) -> PossessionTimeline:
    """White (team 1) is last in control for the whole clip, but only `controlled_frames` have a player at the ball."""
    frames = range(total_frames)
    return PossessionTimeline(
        frame_seconds=0.04,
        controller_by_frame={f: (6 if f < controlled_frames else None) for f in frames},
        team_by_frame={f: 1 for f in frames},  # carried forward while the ball is in flight
    )


def test_possession_warns_when_most_of_it_is_carried_forward_rather_than_observed():
    possession = _timeline(controlled_frames=175, total_frames=750)  # 7 s of control in a 30 s clip

    caveats = ReportBuilder._report_caveats(_TEAM_MODE, possession, possession.team_share())

    assert any("7 s of clear ball control out of a 30 s clip" in c and "only one team" in c for c in caveats)


def test_possession_has_no_warning_with_enough_control_from_both_teams():
    possession = _timeline(controlled_frames=700, total_frames=750)  # 28 s observed
    possession.team_by_frame[0] = 0  # both teams seen

    caveats = ReportBuilder._report_caveats(_TEAM_MODE, possession, possession.team_share())

    assert not any("Possession rests" in c for c in caveats)
