from app.engine.fusion.event_counts import EventCounts
from app.engine.fusion.rating_model import ATTRIBUTES, RatingModel
from app.engine.gemini.schemas import Confidence, EventType, MatchEvent
from tests.factories import kinematics_for


def _event(event_type: EventType, successful: bool) -> MatchEvent:
    return MatchEvent(
        timestamp_s=1.0, event_type=event_type, successful=successful, is_target=True,
        team_kit_color="red", player_description="x", confidence=Confidence.HIGH, description="x",
    )


def test_ratings_stay_in_bounds_without_events():
    ratings = RatingModel().rate(kinematics_for([12.0] * 1500), None, None)
    assert all(30 <= ratings.attributes[a] <= 99 for a in ATTRIBUTES)
    assert 30 <= ratings.overall <= 99
    assert {"SHO", "PAS", "DRI", "DEF"} <= ratings.estimated


def test_faster_player_gets_higher_pace():
    slow = RatingModel().rate(kinematics_for([10.0] * 1500 + [22.0] * 50), None, None)
    fast = RatingModel().rate(kinematics_for([10.0] * 1500 + [32.0] * 50), None, None)
    assert fast.attributes["PAC"] > slow.attributes["PAC"]


def test_shrinkage_keeps_tiny_samples_moderate():
    kin = kinematics_for([12.0] * 1500)
    perfect_two = EventCounts.from_events([_event(EventType.DRIBBLE, True)] * 2)
    perfect_twenty = EventCounts.from_events([_event(EventType.DRIBBLE, True)] * 20)
    two = RatingModel().rate(kin, perfect_two, None).attributes["DRI"]
    twenty = RatingModel().rate(kin, perfect_twenty, None).attributes["DRI"]
    assert two < twenty


def test_event_counts():
    counts = EventCounts.from_events(
        [_event(EventType.PASS, True), _event(EventType.PASS, False), _event(EventType.SHOT, True), _event(EventType.TACKLE, True)]
    )
    assert (counts.passes_attempted, counts.passes_completed) == (2, 1)
    assert counts.pass_accuracy == 0.5
    assert counts.shots_on_target == 1
    assert counts.defensive_actions == 1
