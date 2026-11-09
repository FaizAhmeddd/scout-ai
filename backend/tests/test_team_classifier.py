from app.core.app_config import TeamsConfig
from app.engine.domain.models import OTHER_TEAM
from app.engine.teams.team_classifier import TeamClassifier
from tests.factories import observation


def _track(track_id: int, kits: list[str]):
    return [observation(f, track_id, 100 + f, 500, kit=k) for f, k in enumerate(kits)]


def _fitted(tracks):
    classifier = TeamClassifier(TeamsConfig())
    classifier.fit(tracks)
    return classifier


def test_banded_white_kit_and_numbered_red_kit_are_separated_and_referee_is_other():
    tracks = {i: _track(i, ["white_red_band"] * 30) for i in range(1, 6)}
    tracks |= {i: _track(i, ["red"] * 30) for i in range(6, 9)}
    tracks |= {i: _track(i, ["red_white_number"] * 30) for i in range(9, 11)}  # red players seen from behind
    tracks[20] = _track(20, ["yellow_referee"] * 30)

    teams = _fitted(tracks).assign(tracks)

    white_team = teams.team_of_track[1]
    red_team = teams.team_of_track[6]
    assert white_team != red_team
    assert all(teams.team_of_track[i] == white_team for i in range(1, 6))
    assert all(teams.team_of_track[i] == red_team for i in range(6, 11))
    assert teams.team_of_track[20] == OTHER_TEAM


def test_track_that_swaps_to_an_opponent_is_split():
    tracks = {i: _track(i, ["white_red_band"] * 30) for i in range(1, 5)}
    tracks |= {i: _track(i, ["red"] * 30) for i in range(5, 9)}
    tracks[50] = _track(50, ["white_red_band"] * 40 + ["red"] * 40)

    classifier = _fitted(tracks)
    split = classifier.split_mixed_tracks(tracks)
    teams = classifier.assign(split)

    pieces = sorted(tid for tid, obs in split.items() if tid == 50 or tid > 50)
    assert len(pieces) == 2
    assert teams.team_of_track[pieces[0]] != teams.team_of_track[pieces[1]]


def _role_track(track_id: int, kit: str, foot_x: float, role: str, frames: int = 30):
    observations = [observation(f, track_id, foot_x, 500, kit=kit) for f in range(frames)]
    for obs in observations:
        obs.role = role
    return observations


def test_detected_referee_is_other_even_in_a_team_coloured_kit():
    tracks = {i: _role_track(i, "white_red_band", 100 + 10 * i, "player") for i in range(1, 6)}
    tracks |= {i: _role_track(i, "blue", 900 + 10 * i, "player") for i in range(6, 11)}
    tracks[20] = _role_track(20, "blue", 500, "referee")  # referee kit close to a team's

    teams = _fitted(tracks).assign(tracks)

    assert teams.team_of_track[20] == OTHER_TEAM
    assert teams.team_of_track[1] != teams.team_of_track[6]


def test_goalkeeper_joins_the_team_standing_nearest_to_him():
    tracks = {i: _role_track(i, "white_red_band", 100 + 20 * i, "player") for i in range(1, 6)}  # left side
    tracks |= {i: _role_track(i, "blue", 1500 + 20 * i, "player") for i in range(6, 11)}  # right side
    tracks[30] = _role_track(30, "yellow_referee", 40, "goalkeeper")  # own kit, among the white team
    tracks[31] = _role_track(31, "red", 1800, "goalkeeper")  # own kit, among the blue team

    classifier = _fitted(tracks)
    teams = classifier.assign(classifier.split_mixed_tracks(tracks))

    assert teams.team_of_track[30] == teams.team_of_track[1]
    assert teams.team_of_track[31] == teams.team_of_track[6]
