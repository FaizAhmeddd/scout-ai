from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    PASS = "pass"
    CROSS = "cross"
    SHOT = "shot"
    DRIBBLE = "dribble"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    CLEARANCE = "clearance"
    BLOCK = "block"
    AERIAL_DUEL = "aerial_duel"
    GROUND_DUEL = "ground_duel"
    BALL_RECOVERY = "ball_recovery"
    POSSESSION_LOST = "possession_lost"
    FOUL_COMMITTED = "foul_committed"
    FOUL_WON = "foul_won"
    CARD = "card"
    SAVE = "save"


class PassLength(str, Enum):
    SHORT = "short"
    LONG = "long"
    NOT_A_PASS = "not_a_pass"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MatchEvent(BaseModel):
    timestamp_s: float = Field(description="Seconds from the start of the video when the action happens")
    event_type: EventType
    successful: bool = Field(
        description="pass/cross completed to a team-mate, shot on target, dribble beat the opponent, "
        "tackle/duel won, save made; false otherwise"
    )
    is_target: bool = Field(description="True if performed by the target player (player mode) or target team (team mode)")
    team_kit_color: str = Field(description="Shirt colour of the team performing the action")
    player_jersey: int | None = Field(default=None, description="Jersey number if legible, else null")
    player_description: str = Field(description="Short visual description of who performed it")
    pass_length: PassLength = PassLength.NOT_A_PASS
    progressive: bool = Field(default=False, description="Moves the ball at least ~10 m closer to the opponent goal")
    key_pass: bool = Field(default=False, description="Pass that directly creates a shot")
    goal: bool = False
    assist: bool = False
    card_color: str | None = Field(default=None, description="yellow or red for card events")
    confidence: Confidence
    description: str


class FourCornerAssessment(BaseModel):
    technical: float = Field(description="0-10: first touch, passing, dribbling, shooting technique")
    tactical: float = Field(description="0-10: positioning, scanning, decision-making, off-ball movement")
    physical: float = Field(description="0-10: pace, strength, stamina, work-rate as observed")
    mental: float = Field(description="0-10: composure, concentration, aggression in duels, reaction to errors")


class PlayerAssessment(BaseModel):
    player_jersey: int | None = None
    player_description: str
    approximate_position: str = Field(description="e.g. Goalkeeper, Centre-back, Full-back, Defensive midfielder, Winger, Striker")
    four_corner: FourCornerAssessment
    overall_rating_10: float = Field(description="Holistic match rating 0-10 (6.0 = average)")
    strengths: list[str]
    areas_to_improve: list[str]
    summary: str


class KeyMoment(BaseModel):
    timestamp_s: float
    title: str
    description: str


class GeminiMatchAnalysis(BaseModel):
    target_identified: bool = Field(description="Whether the target player/team could be confidently identified")
    identification_notes: str
    events: list[MatchEvent]
    assessments: list[PlayerAssessment]
    tactical_summary: str
    key_moments: list[KeyMoment]
    caveats: str = Field(description="Visibility problems, camera cuts, or anything that limits accuracy")
