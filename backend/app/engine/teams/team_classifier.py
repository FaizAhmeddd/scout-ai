import logging
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans

from app.core.app_config import TeamsConfig
from app.engine.domain.models import (
    OTHER_TEAM,
    ROLE_GOALKEEPER,
    ROLE_PLAYER,
    ROLE_REFEREE,
    PlayerObservation,
    TeamAssignment,
    track_role,
)
from app.engine.render.palette import describe_color, lab_to_bgr

logger = logging.getLogger(__name__)

# Kits are compared by colour proportions (Euclidean distance between histograms; 0 = identical,
# sqrt(2) = disjoint). Proportions rather than sqrt/Hellinger, which would inflate minority colours and
# make a white kit with a red band look like a red kit with a white number.
_MIN_OUTLIER_DISTANCE = 0.12

Tracks = dict[int, list[PlayerObservation]]


def shirt_feature(hist: np.ndarray) -> np.ndarray:
    return hist


class TeamClassifier:
    """Learns the two kits, repairs tracks that swapped between opponents, and assigns teams.

    Kits are compared as colour histograms (proportion of each hue / white / black), so a red shirt with a
    big white number and a white shirt with a red band stay apart. Tracks far from both kits become
    OTHER_TEAM. When the detector labels roles, referees are always OTHER_TEAM and goalkeepers (own kit) join
    the team whose outfield players stand nearest to them, frame by frame.
    """

    def __init__(self, config: TeamsConfig):
        self.config = config
        self._centers: np.ndarray | None = None
        self._thresholds: np.ndarray | None = None

    def fit(self, tracks: Tracks) -> None:
        features = self._track_features(_outfield(tracks))
        reliable = {tid: f for tid, (f, n) in features.items() if n >= self.config.min_track_observations}
        if len(reliable) < self.config.n_teams:
            raise RuntimeError(
                f"Only {len(reliable)} reliably coloured players found - not enough to separate teams. "
                "Is this a football broadcast clip with visible players?"
            )

        ids = list(reliable)
        weights = np.array([features[t][1] for t in ids], dtype=np.float32)
        x = np.stack([reliable[t] for t in ids])
        kmeans = KMeans(n_clusters=self.config.n_teams, n_init=10, random_state=0)
        labels = kmeans.fit_predict(x, sample_weight=weights)

        presence = [weights[labels == c].sum() for c in range(self.config.n_teams)]
        order = np.argsort(presence)[::-1]  # team 0 = the kit seen most
        self._centers = kmeans.cluster_centers_[order]
        team_labels = np.argsort(order)[labels]

        thresholds = []
        for team in range(self.config.n_teams):
            spread = np.median(np.linalg.norm(x[team_labels == team] - self._centers[team], axis=1))
            thresholds.append(max(self.config.outlier_distance_factor * spread, _MIN_OUTLIER_DISTANCE))
        self._thresholds = np.array(thresholds)

    def split_mixed_tracks(self, tracks: Tracks) -> Tracks:
        """Cuts a track wherever its shirt consistently switches to the other kit (tracker ID swap)."""
        self._require_fit()
        result: Tracks = {}
        next_id = max(tracks, default=0) + 1
        splits = 0
        for tid, observations in tracks.items():
            if track_role(observations) != ROLE_PLAYER:
                result[tid] = observations  # goalkeeper / referee kits match neither team: nothing to split
                continue
            segments = self._kit_segments(observations)
            result[tid] = segments[0]
            for segment in segments[1:]:
                for obs in segment:
                    obs.track_id = next_id
                result[next_id] = segment
                next_id += 1
                splits += 1
        logger.info("Split %d tracker ID swaps between opposing players", splits)
        return result

    def assign(self, tracks: Tracks) -> TeamAssignment:
        self._require_fit()
        roles = {tid: track_role(observations) for tid, observations in tracks.items()}
        team_of_track = {
            tid: self._nearest_team(feature) if roles[tid] == ROLE_PLAYER else OTHER_TEAM
            for tid, (feature, _) in self._track_features(tracks).items()
        }
        for tid in tracks:
            team_of_track.setdefault(tid, OTHER_TEAM)

        centers_lab = self._team_display_colors(tracks, team_of_track)  # outfield kits only
        if self.config.goalkeepers_by_position:
            positions = _team_positions_by_frame(tracks, team_of_track)
            for tid, observations in tracks.items():
                if roles[tid] == ROLE_GOALKEEPER:
                    team_of_track[tid] = _nearest_team_by_position(observations, positions, self.config.n_teams)
        referees = sum(role == ROLE_REFEREE for role in roles.values())
        if referees:
            logger.info("Excluded %d referee tracks from the teams", referees)

        colors = {team: lab_to_bgr(lab) for team, lab in centers_lab.items()}
        names = self._distinct_names({team: describe_color(bgr) for team, bgr in colors.items()})
        logger.info("Teams: %s", names)
        return TeamAssignment(team_of_track=team_of_track, colors_bgr=colors, color_names=names, centers_lab=centers_lab)

    def _nearest_team(self, feature: np.ndarray) -> int:
        distances = np.linalg.norm(self._centers - feature, axis=1)
        team = int(np.argmin(distances))
        return team if distances[team] <= self._thresholds[team] else OTHER_TEAM

    def _kit_segments(self, observations: list[PlayerObservation]) -> list[list[PlayerObservation]]:
        labels: list[int | None] = []
        last = None
        for obs in observations:
            if obs.torso_hist is not None:
                last = int(np.argmin(np.linalg.norm(self._centers - shirt_feature(obs.torso_hist), axis=1)))
            labels.append(last)
        if all(label is None for label in labels):
            return [observations]

        window = self.config.switch_min_observations
        smoothed = _rolling_majority(labels, window)
        segments, start = [], 0
        for i in range(1, len(smoothed)):
            if smoothed[i] != smoothed[i - 1]:
                segments.append(observations[start:i])
                start = i
        segments.append(observations[start:])

        merged: list[list[PlayerObservation]] = []
        for segment in segments:
            if merged and len(segment) < window:
                merged[-1].extend(segment)
            else:
                merged.append(list(segment))
        return merged

    def _track_features(self, tracks: Tracks) -> dict[int, tuple[np.ndarray, int]]:
        features = {}
        for tid, observations in tracks.items():
            hists = [o.torso_hist for o in observations if o.torso_hist is not None]
            if not hists:
                continue
            if len(hists) > self.config.max_samples_per_track:
                step = len(hists) / self.config.max_samples_per_track
                hists = [hists[int(i * step)] for i in range(self.config.max_samples_per_track)]
            features[tid] = (shirt_feature(np.mean(np.stack(hists), axis=0)), len(hists))
        return features

    def _team_display_colors(self, tracks: Tracks, team_of_track: dict[int, int]) -> dict[int, np.ndarray]:
        colors = {}
        for team in range(len(self._centers)):
            labs = [
                o.torso_color_lab
                for tid, obs in tracks.items() if team_of_track.get(tid) == team
                for o in obs[:: max(len(obs) // 20, 1)] if o.torso_color_lab is not None
            ]
            colors[team] = np.median(np.stack(labs), axis=0) if labs else np.array([50.0, 0.0, 0.0])
        return colors

    @staticmethod
    def _distinct_names(names: dict[int, str]) -> dict[int, str]:
        if len(set(names.values())) == len(names):
            return names
        return {team: f"{name} ({'home' if team == 0 else 'away'})" for team, name in names.items()}

    def _require_fit(self) -> None:
        if self._centers is None:
            raise RuntimeError("TeamClassifier.fit() must be called first")


def _outfield(tracks: Tracks) -> Tracks:
    """Tracks the detector saw as outfield players (all tracks when it does not label roles)."""
    outfield = {tid: obs for tid, obs in tracks.items() if track_role(obs) == ROLE_PLAYER}
    return outfield or tracks


def _team_positions_by_frame(tracks: Tracks, team_of_track: dict[int, int]) -> dict[int, dict[int, list[np.ndarray]]]:
    positions: dict[int, dict[int, list[np.ndarray]]] = {}
    for tid, observations in tracks.items():
        team = team_of_track.get(tid, OTHER_TEAM)
        if team == OTHER_TEAM:
            continue
        for obs in observations:
            positions.setdefault(obs.frame_idx, {}).setdefault(team, []).append(obs.foot_point())
    return positions


def _nearest_team_by_position(
    observations: list[PlayerObservation], positions: dict[int, dict[int, list[np.ndarray]]], n_teams: int
) -> int:
    """Votes, frame by frame, for the team whose players' centroid is nearest (a keeper stands among his defenders).

    Compared within each frame, so camera panning does not matter.
    """
    votes: Counter[int] = Counter()
    for obs in observations:
        teams = positions.get(obs.frame_idx, {})
        if len(teams) < n_teams:
            continue
        foot = obs.foot_point()
        distances = {team: float(np.linalg.norm(np.mean(points, axis=0) - foot)) for team, points in teams.items()}
        votes[min(distances, key=distances.get)] += 1
    return votes.most_common(1)[0][0] if votes else OTHER_TEAM


def _rolling_majority(labels: list[int | None], window: int) -> list[int]:
    filled, last = [], None
    for label in labels:
        last = label if label is not None else last
        filled.append(last)
    first_known = next(label for label in filled if label is not None)
    filled = [first_known if label is None else label for label in filled]

    half = window // 2
    result = []
    for i in range(len(filled)):
        chunk = filled[max(0, i - half): i + half + 1]
        result.append(max(set(chunk), key=chunk.count))
    return result
