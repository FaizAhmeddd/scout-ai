from collections.abc import Iterable
from dataclasses import asdict, dataclass

from app.engine.gemini.schemas import EventType, MatchEvent, PassLength


@dataclass
class EventCounts:
    passes_attempted: int = 0
    passes_completed: int = 0
    short_passes: int = 0
    long_passes: int = 0
    long_passes_completed: int = 0
    progressive_passes: int = 0
    key_passes: int = 0
    assists: int = 0
    crosses_attempted: int = 0
    crosses_completed: int = 0
    shots: int = 0
    shots_on_target: int = 0
    goals: int = 0
    dribbles_attempted: int = 0
    dribbles_successful: int = 0
    tackles_attempted: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    clearances: int = 0
    blocks: int = 0
    ball_recoveries: int = 0
    aerial_duels: int = 0
    aerial_duels_won: int = 0
    ground_duels: int = 0
    ground_duels_won: int = 0
    possession_lost: int = 0
    fouls_committed: int = 0
    fouls_won: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    saves: int = 0

    @classmethod
    def from_events(cls, events: Iterable[MatchEvent]) -> "EventCounts":
        counts = cls()
        for event in events:
            counts._add(event)
        return counts

    def _add(self, e: MatchEvent) -> None:
        ok = e.successful
        match e.event_type:
            case EventType.PASS:
                self.passes_attempted += 1
                self.passes_completed += ok
                if e.pass_length == PassLength.LONG:
                    self.long_passes += 1
                    self.long_passes_completed += ok
                else:
                    self.short_passes += 1
                self.progressive_passes += e.progressive
                self.key_passes += e.key_pass
                self.assists += e.assist
            case EventType.CROSS:
                self.crosses_attempted += 1
                self.crosses_completed += ok
                self.key_passes += e.key_pass
                self.assists += e.assist
            case EventType.SHOT:
                self.shots += 1
                self.shots_on_target += ok or e.goal
                self.goals += e.goal
            case EventType.DRIBBLE:
                self.dribbles_attempted += 1
                self.dribbles_successful += ok
            case EventType.TACKLE:
                self.tackles_attempted += 1
                self.tackles_won += ok
            case EventType.INTERCEPTION:
                self.interceptions += 1
            case EventType.CLEARANCE:
                self.clearances += 1
            case EventType.BLOCK:
                self.blocks += 1
            case EventType.BALL_RECOVERY:
                self.ball_recoveries += 1
            case EventType.AERIAL_DUEL:
                self.aerial_duels += 1
                self.aerial_duels_won += ok
            case EventType.GROUND_DUEL:
                self.ground_duels += 1
                self.ground_duels_won += ok
            case EventType.POSSESSION_LOST:
                self.possession_lost += 1
            case EventType.FOUL_COMMITTED:
                self.fouls_committed += 1
            case EventType.FOUL_WON:
                self.fouls_won += 1
            case EventType.CARD:
                if (e.card_color or "").lower().startswith("r"):
                    self.red_cards += 1
                else:
                    self.yellow_cards += 1
            case EventType.SAVE:
                self.saves += 1

    @property
    def pass_accuracy(self) -> float | None:
        return self.passes_completed / self.passes_attempted if self.passes_attempted else None

    @property
    def dribble_success(self) -> float | None:
        return self.dribbles_successful / self.dribbles_attempted if self.dribbles_attempted else None

    @property
    def duels(self) -> int:
        return self.aerial_duels + self.ground_duels + self.tackles_attempted

    @property
    def duels_won(self) -> int:
        return self.aerial_duels_won + self.ground_duels_won + self.tackles_won

    @property
    def defensive_actions(self) -> int:
        return self.tackles_won + self.interceptions + self.clearances + self.blocks + self.ball_recoveries

    def as_dict(self) -> dict[str, int]:
        return asdict(self)
