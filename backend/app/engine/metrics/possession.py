from dataclasses import dataclass, field

import numpy as np

from app.core.app_config import PossessionConfig
from app.engine.domain.models import OTHER_TEAM, BallObservation, PlayerObservation, PlayerTrack


@dataclass
class PossessionSpell:
    player_id: int
    team_id: int
    start_frame: int
    end_frame: int


@dataclass
class PossessionTimeline:
    frame_seconds: float
    controller_by_frame: dict[int, int | None] = field(default_factory=dict)
    team_by_frame: dict[int, int | None] = field(default_factory=dict)
    spells: list[PossessionSpell] = field(default_factory=list)

    def player_possession_s(self, player_id: int) -> float:
        return sum(1 for p in self.controller_by_frame.values() if p == player_id) * self.frame_seconds

    def player_touches(self, player_id: int) -> int:
        return sum(1 for spell in self.spells if spell.player_id == player_id)

    def team_share(self) -> dict[int, float]:
        teams = [t for t in self.team_by_frame.values() if t is not None]
        if not teams:
            return {}
        values, counts = np.unique(teams, return_counts=True)
        return {int(v): float(c) / len(teams) for v, c in zip(values, counts)}

    def rolling_team_share(self, frames: list[int], team_id: int, window: int) -> np.ndarray:
        indicator = np.array(
            [np.nan if self.team_by_frame.get(f) is None else float(self.team_by_frame[f] == team_id) for f in frames]
        )
        kernel = np.ones(window)
        valid = np.convolve(~np.isnan(indicator), kernel, mode="same")
        total = np.convolve(np.nan_to_num(indicator), kernel, mode="same")
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(valid > 0, total / valid, np.nan)


class PossessionAnalyzer:
    """Assigns the ball to the closest player's feet (ankle keypoints) within a body-height-scaled radius."""

    def __init__(self, config: PossessionConfig, min_keypoint_conf: float, frame_seconds: float):
        self.config = config
        self.min_keypoint_conf = min_keypoint_conf
        self.frame_seconds = frame_seconds

    def analyze(
        self, players: list[PlayerTrack], balls: dict[int, BallObservation], processed_frames: list[int]
    ) -> PossessionTimeline:
        by_frame: dict[int, list[tuple[PlayerTrack, PlayerObservation]]] = {}
        for player in players:
            if player.team_id == OTHER_TEAM:
                continue
            for obs in player.observations:
                by_frame.setdefault(obs.frame_idx, []).append((player, obs))

        timeline = PossessionTimeline(frame_seconds=self.frame_seconds)
        team_of = {p.player_id: p.team_id for p in players}
        controller: int | None = None
        team: int | None = None
        candidate: int | None = None
        streak = 0
        spell_start = 0

        for frame_idx in processed_frames:
            nearest = self._nearest_player(balls.get(frame_idx), by_frame.get(frame_idx, []))
            if nearest is not None and nearest != controller:
                streak = streak + 1 if nearest == candidate else 1
                candidate = nearest
                if streak >= self.config.min_consecutive_frames:
                    if controller is not None:
                        timeline.spells.append(PossessionSpell(controller, team_of[controller], spell_start, frame_idx))
                    controller, team, spell_start = nearest, team_of[nearest], frame_idx
            elif nearest == controller:
                candidate, streak = None, 0
            timeline.controller_by_frame[frame_idx] = controller if nearest == controller else None
            timeline.team_by_frame[frame_idx] = team

        if controller is not None and processed_frames:
            timeline.spells.append(PossessionSpell(controller, team_of[controller], spell_start, processed_frames[-1]))
        return timeline

    def _nearest_player(
        self, ball: BallObservation | None, candidates: list[tuple[PlayerTrack, PlayerObservation]]
    ) -> int | None:
        if ball is None or not candidates:
            return None
        best_id, best_ratio = None, np.inf
        for player, obs in candidates:
            distance = min(float(np.linalg.norm(ball.center - f)) for f in obs.feet(self.min_keypoint_conf))
            radius = self.config.control_radius_body_heights * obs.body_height_px(self.min_keypoint_conf)
            ratio = distance / max(radius, 1.0)
            if ratio <= 1.0 and ratio < best_ratio:
                best_id, best_ratio = player.player_id, ratio
        return best_id
