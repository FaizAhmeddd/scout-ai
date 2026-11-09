from dataclasses import dataclass, field

import numpy as np

from app.engine.fusion.event_counts import EventCounts
from app.engine.gemini.schemas import PlayerAssessment
from app.engine.metrics.kinematics import KinematicProfile

ATTRIBUTES = ("PAC", "SHO", "PAS", "DRI", "DEF", "PHY")

# Position-group weights for the overall rating, mirroring how FC/FIFA weights attributes by role.
_POSITION_WEIGHTS: dict[str, dict[str, float]] = {
    "ATT": {"PAC": 0.20, "SHO": 0.30, "PAS": 0.15, "DRI": 0.25, "DEF": 0.00, "PHY": 0.10},
    "MID": {"PAC": 0.10, "SHO": 0.10, "PAS": 0.30, "DRI": 0.20, "DEF": 0.15, "PHY": 0.15},
    "DEF": {"PAC": 0.15, "SHO": 0.00, "PAS": 0.15, "DRI": 0.05, "DEF": 0.45, "PHY": 0.20},
}
_POSITION_KEYWORDS = {
    "ATT": ("striker", "forward", "winger", "attack", "centre-forward", "center-forward"),
    "DEF": ("back", "defender", "goalkeeper", "keeper", "sweeper"),
    "MID": ("midfield",),
}
_POSITION_ABBREVIATIONS = {
    "goalkeeper": "GK", "keeper": "GK", "centre-back": "CB", "center-back": "CB", "full-back": "FB",
    "left-back": "LB", "right-back": "RB", "wing-back": "WB", "defensive midfielder": "CDM",
    "central midfielder": "CM", "attacking midfielder": "CAM", "midfielder": "CM", "winger": "W",
    "left winger": "LW", "right winger": "RW", "striker": "ST", "forward": "ST",
}
_SHRINK_STRENGTH = 5.0
_ASSESSMENT_BLEND = 0.25
_NEUTRAL = 55.0


@dataclass
class FifaRatings:
    attributes: dict[str, int]
    overall: int
    position: str
    position_group: str
    estimated: set[str] = field(default_factory=set)  # attributes with too little evidence


class RatingModel:
    """FIFA/FC-style 0-99 attributes from tracking (physical) and Gemini events (technical/defensive).

    Rates are shrunk towards league-typical priors so a handful of events cannot produce extreme scores,
    and per-10-minute volumes are normalised by the player's on-screen time.
    """

    def rate(
        self,
        kinematics: KinematicProfile,
        counts: EventCounts | None,
        assessment: PlayerAssessment | None,
    ) -> FifaRatings:
        minutes = max(kinematics.time_tracked_s / 60, 1.0)
        per10 = lambda value: value / minutes * 10  # noqa: E731
        technical = assessment.four_corner.technical if assessment else None
        estimated: set[str] = set()

        pace = 0.75 * _scale(kinematics.top_speed_kmh, 18, 34) + 0.25 * _scale(per10(len(kinematics.sprints)), 0, 5)
        high_intensity_share = (
            kinematics.high_intensity_distance_m / kinematics.total_distance_m if kinematics.total_distance_m else 0.0
        )
        physical_parts = [
            (0.45, _scale(kinematics.distance_per_min, 50, 130)),
            (0.25, _scale(high_intensity_share, 0.02, 0.18)),
            (0.15, _scale(per10(kinematics.accelerations + kinematics.decelerations), 0, 14)),
        ]

        if counts is None:
            attrs = {name: _NEUTRAL for name in ("SHO", "PAS", "DRI", "DEF")}
            if technical is not None:
                attrs = {name: _scale(technical, 3, 9) for name in attrs}
            estimated.update(attrs)
            physical_parts.append((0.15, _NEUTRAL))
        else:
            attrs = self._event_attributes(counts, per10, technical, estimated)
            duel_rate = _shrunk_rate(counts.duels_won, counts.duels, prior=0.5)
            physical_parts.append((0.15, _scale(duel_rate, 0.3, 0.7)))

        attrs["PAC"] = pace
        attrs["PHY"] = sum(w * v for w, v in physical_parts)
        if kinematics.time_tracked_s < 20:
            estimated.update({"PAC", "PHY"})

        group, position = self._position(assessment)
        weights = _POSITION_WEIGHTS[group]
        overall = sum(weights[name] * attrs[name] for name in ATTRIBUTES)
        if assessment is not None:
            overall = (1 - _ASSESSMENT_BLEND) * overall + _ASSESSMENT_BLEND * _scale(assessment.overall_rating_10, 4, 9)

        return FifaRatings(
            attributes={name: int(round(np.clip(attrs[name], 30, 99))) for name in ATTRIBUTES},
            overall=int(round(np.clip(overall, 30, 99))),
            position=position,
            position_group=group,
            estimated=estimated,
        )

    def _event_attributes(self, c: EventCounts, per10, technical: float | None, estimated: set[str]) -> dict[str, float]:
        tech_score = _scale(technical, 3, 9) if technical is not None else _NEUTRAL

        if c.shots == 0:
            shooting = 0.6 * _NEUTRAL + 0.4 * tech_score - 5
            estimated.add("SHO")
        else:
            on_target = _shrunk_rate(c.shots_on_target, c.shots, prior=0.35)
            shooting = (
                0.35 * _scale(per10(c.shots), 0, 3)
                + 0.45 * _scale(on_target, 0.15, 0.75)
                + 0.20 * tech_score
                + 6 * c.goals
            )

        if c.passes_attempted + c.crosses_attempted == 0:
            passing = tech_score
            estimated.add("PAS")
        else:
            accuracy = _shrunk_rate(c.passes_completed + c.crosses_completed, c.passes_attempted + c.crosses_attempted, prior=0.75)
            passing = (
                0.55 * _scale(accuracy, 0.55, 0.93)
                + 0.15 * _scale(per10(c.key_passes), 0, 2)
                + 0.15 * _scale(per10(c.progressive_passes), 0, 4)
                + 0.15 * _scale(per10(c.passes_attempted), 0, 12)
                + 5 * c.assists
            )

        if c.dribbles_attempted == 0:
            dribbling = 0.5 * tech_score + 0.5 * _NEUTRAL
            estimated.add("DRI")
        else:
            success = _shrunk_rate(c.dribbles_successful, c.dribbles_attempted, prior=0.5)
            dribbling = (
                0.45 * _scale(success, 0.25, 0.8)
                + 0.25 * _scale(per10(c.dribbles_attempted), 0, 4)
                + 0.30 * tech_score
            )

        if c.defensive_actions + c.tackles_attempted == 0:
            defending = _NEUTRAL - 10
            estimated.add("DEF")
        else:
            defending = (
                0.45 * _scale(per10(c.defensive_actions), 0, 6)
                + 0.30 * _scale(_shrunk_rate(c.tackles_won, c.tackles_attempted, prior=0.55), 0.3, 0.8)
                + 0.25 * _scale(_shrunk_rate(c.duels_won, c.duels, prior=0.5), 0.3, 0.7)
            )
        return {"SHO": shooting, "PAS": passing, "DRI": dribbling, "DEF": defending}

    @staticmethod
    def _position(assessment: PlayerAssessment | None) -> tuple[str, str]:
        if assessment is None:
            return "MID", "--"
        text = assessment.approximate_position.lower()
        position = next((abbr for name, abbr in sorted(_POSITION_ABBREVIATIONS.items(), key=lambda kv: -len(kv[0])) if name in text), "--")
        for group in ("DEF", "ATT", "MID"):
            if any(word in text for word in _POSITION_KEYWORDS[group]):
                return group, position
        return "MID", position


def _scale(value: float | None, low: float, high: float, out_low: float = 40.0, out_high: float = 95.0) -> float:
    if value is None:
        return _NEUTRAL
    t = (value - low) / (high - low)
    return out_low + float(np.clip(t, 0, 1)) * (out_high - out_low)


def _shrunk_rate(successes: int, attempts: int, prior: float) -> float:
    return (successes + prior * _SHRINK_STRENGTH) / (attempts + _SHRINK_STRENGTH)
