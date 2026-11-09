from dataclasses import dataclass, field


@dataclass
class GeminiTargetContext:
    mode: str  # "player" | "team"
    team_color: str
    opponent_color: str
    video_duration_s: float
    jersey_number: int | None = None
    player_label: str = ""
    visible_windows: list[tuple[float, float]] = field(default_factory=list)
    reference_image_jpeg: bytes | None = None


_ROLE = """You are an elite football (soccer) performance analyst producing professional-grade event data, \
equivalent to what Opta/StatsBomb analysts log, from broadcast match video. You work agentically: plan your \
viewing, scan the whole video first, then revisit every relevant segment at full temporal resolution before \
logging an event. Accuracy matters more than volume."""

_EVENT_RULES = """Event logging rules (apply strictly):
- pass: any deliberate ball played to a team-mate (successful = reaches a team-mate). Set pass_length "long" \
for passes of roughly 30 m or more, else "short". Mark progressive passes and key passes (leading directly to a shot).
- cross: ball delivered from a wide area into the penalty box.
- shot: any attempt on goal (successful = on target). Set goal=true when it scores.
- dribble: deliberately taking on an opponent with the ball (successful = beats them and keeps the ball).
- tackle: dispossessing an opponent who has the ball (successful = ball won or cleared).
- interception, clearance, block, ball_recovery: log as seen (successful = true).
- aerial_duel / ground_duel: 50-50 contests (successful = won).
- possession_lost: miscontrol or being dispossessed (successful = false).
- foul_committed / foul_won / card / save: as seen.
- timestamp_s is seconds from the start of THIS video. Every event needs one.
- If an action is ambiguous, still log it but set confidence to "low". Never invent events you did not see.
- Ignore replays: if the broadcast shows a replay, do not log its actions a second time."""


_STYLE = """Writing style (strict): every text field is shown on a dashboard, so be brief and quantified.
- Bullets, not paragraphs. Each strength / area to improve is ONE line of at most 12 words: lead with the impact \
and cite a number or timestamp (e.g. "Won 3 of 4 duels, 0:06-0:14").
- summary: 2 sentences, at most 40 words. tactical_summary: at most 2 sentences.
- key_moments: title at most 5 words, description at most 15 words.
- Event description: at most 12 words. caveats and identification_notes: one short sentence each.
- No filler, no repeating a point, no restating event counts that the event log already shows."""


def build_prompt(context: GeminiTargetContext) -> str:
    duration = f"The video is {context.video_duration_s:.0f} seconds long."
    if context.mode == "player":
        return "\n\n".join([_ROLE, duration, _player_target(context), _EVENT_RULES, _player_output(context), _STYLE])
    return "\n\n".join([_ROLE, duration, _team_target(context), _EVENT_RULES, _team_output(context), _STYLE])


def _player_target(context: GeminiTargetContext) -> str:
    jersey = f"wearing number {context.jersey_number}" if context.jersey_number is not None else "(jersey number unknown — read it if visible)"
    windows = ", ".join(f"{_mmss(a)}-{_mmss(b)}" for a, b in context.visible_windows[:25]) or "throughout"
    reference = (
        "A reference image cropped from the video is attached: that is the TARGET PLAYER. "
        if context.reference_image_jpeg
        else ""
    )
    return f"""TARGET: a single player of the team in {context.team_color} shirts, {jersey}. \
The opponents wear {context.opponent_color}. {reference}Our tracking system saw this player on screen during \
these windows (mm:ss): {windows}. Use them to find the player quickly, but also check the rest of the video.

Log EVERY on-ball and defensive action of the target player (is_target=true). Also log the opponent \
actions that directly involve the target player (e.g. a tackle on them) with is_target=false."""


def _team_target(context: GeminiTargetContext) -> str:
    return f"""TARGET: the whole team in {context.team_color} shirts (opponents wear {context.opponent_color}). \
Log every on-ball and defensive action of the target team's players (is_target=true), reading jersey numbers \
whenever they are legible. Also log opponent shots, goals and cards with is_target=false."""


def _player_output(context: GeminiTargetContext) -> str:
    return """Then provide exactly ONE entry in `assessments` for the target player: the four-corner rating \
(technical, tactical, physical, mental, each 0-10), an overall_rating_10 (6.0 = average professional \
performance), approximate position, 2-3 strengths and 2-3 areas to improve grounded in specific observed \
actions (cite timestamps), and a 2-sentence scouting summary.
Add 3-6 key_moments involving the target, a tactical_summary of the player's role and movement, and \
honest caveats (occlusion, camera angle, cuts). If you cannot identify the player, set target_identified=false \
and explain in identification_notes."""


def _team_output(context: GeminiTargetContext) -> str:
    return """Then provide one entry in `assessments` for every target-team player you could follow for a \
meaningful time (identify by jersey number when legible, otherwise by position and appearance), each with the \
four-corner rating, overall_rating_10, approximate position, strengths, areas to improve and a short summary.
Add 4-6 key_moments, a tactical_summary of the team's shape, pressing, build-up and transitions, and honest caveats."""


def _mmss(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
