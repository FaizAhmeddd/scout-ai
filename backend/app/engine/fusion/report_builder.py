from dataclasses import dataclass, field

import numpy as np

from app.engine.domain.models import AnalysisTarget, PlayerTrack, TeamAssignment, VideoInfo
from app.engine.fusion.event_counts import EventCounts
from app.engine.fusion.rating_model import FifaRatings, RatingModel
from app.engine.gemini.schemas import GeminiMatchAnalysis, MatchEvent, PlayerAssessment
from app.engine.geometry.view_transformer import PositionSeries
from app.engine.metrics.ball_path import BallPath
from app.engine.metrics.kinematics import KinematicProfile
from app.engine.metrics.pose_metrics import PoseProfile
from app.engine.metrics.possession import PossessionTimeline

_EVENT_POSITION_TOLERANCE_S = 1.0
_MIN_REPORTED_ON_SCREEN_S = 2.0  # shorter identities are tracker fragments, not a player's match
_MIN_POSSESSION_SAMPLE_S = 20.0  # less clear ball control than this makes the possession share indicative only


@dataclass
class PlayerMetrics:
    """Everything measured for one player from tracking + pose (no Gemini)."""

    player: PlayerTrack
    series: PositionSeries
    kinematics: KinematicProfile
    pose: PoseProfile
    on_screen_s: float


@dataclass
class PlayerReport:
    metrics: PlayerMetrics
    label: str
    jersey_number: int | None
    possession_s: float
    touches: int
    ratings: FifaRatings
    counts: EventCounts | None = None
    events: list[MatchEvent] = field(default_factory=list)
    event_positions: list[tuple[MatchEvent, np.ndarray | None]] = field(default_factory=list)
    assessment: PlayerAssessment | None = None

    @property
    def player_id(self) -> int:
        return self.metrics.player.player_id


@dataclass
class TeamReport:
    team_id: int
    color_name: str
    color_bgr: tuple[int, int, int]
    players: list[PlayerReport]
    possession_share: float | None
    counts: EventCounts | None
    events: list[MatchEvent]
    assessments: list[PlayerAssessment]


@dataclass
class MatchReport:
    video: VideoInfo
    target: AnalysisTarget
    geometry_mode: str
    pitch_coordinates: bool
    focus_team: TeamReport
    opponent_color: str
    possession: PossessionTimeline
    focus_player: PlayerReport | None
    gemini: GeminiMatchAnalysis | None
    gemini_status: str
    caveats: list[str]
    ball_path: BallPath | None = None


class ReportBuilder:
    """Fuses tracking/pose metrics with Gemini's event log into player and team reports."""

    def __init__(self, rating_model: RatingModel, video: VideoInfo):
        self.rating_model = rating_model
        self.video = video

    def build(
        self,
        target: AnalysisTarget,
        teams: TeamAssignment,
        metrics: dict[int, PlayerMetrics],
        possession: PossessionTimeline,
        gemini: GeminiMatchAnalysis | None,
        gemini_status: str,
        geometry_mode: str,
        pitch_coordinates: bool,
        ball_path: BallPath | None = None,
    ) -> MatchReport:
        target_events = [e for e in gemini.events if e.is_target] if gemini else []
        team_players = [
            m for m in metrics.values()
            if m.player.team_id == target.team_id
            and (m.on_screen_s >= _MIN_REPORTED_ON_SCREEN_S or m.player.player_id == target.player_id)
        ]
        share = possession.team_share()

        focus_player = None
        player_reports = []
        for m in sorted(team_players, key=lambda m: -m.on_screen_s):
            is_focus = target.is_player_mode and m.player.player_id == target.player_id
            report = self._player_report(m, target, possession, gemini, target_events if is_focus else None)
            player_reports.append(report)
            if is_focus:
                focus_player = report

        opponent_id = next((t for t in teams.color_names if t != target.team_id), None)
        focus_team = TeamReport(
            team_id=target.team_id,
            color_name=teams.color_names[target.team_id],
            color_bgr=teams.colors_bgr[target.team_id],
            players=player_reports,
            possession_share=share.get(target.team_id, 0.0) if share else None,
            counts=EventCounts.from_events(target_events) if gemini and not target.is_player_mode else None,
            events=target_events if not target.is_player_mode else [],
            assessments=gemini.assessments if gemini and not target.is_player_mode else [],
        )
        return MatchReport(
            video=self.video,
            target=target,
            geometry_mode=geometry_mode,
            pitch_coordinates=pitch_coordinates,
            focus_team=focus_team,
            opponent_color=teams.color_names.get(opponent_id, "unknown") if opponent_id is not None else "unknown",
            possession=possession,
            focus_player=focus_player,
            gemini=gemini,
            gemini_status=gemini_status,
            caveats=self._caveats(geometry_mode, gemini, gemini_status) + self._report_caveats(target, possession, share),
            ball_path=ball_path,
        )

    def _player_report(
        self,
        m: PlayerMetrics,
        target: AnalysisTarget,
        possession: PossessionTimeline,
        gemini: GeminiMatchAnalysis | None,
        events: list[MatchEvent] | None,
    ) -> PlayerReport:
        is_focus = events is not None
        assessment = gemini.assessments[0] if is_focus and gemini and gemini.assessments else None
        counts = EventCounts.from_events(events) if is_focus and gemini else None
        report = PlayerReport(
            metrics=m,
            label=target.label if is_focus and target.label else f"Player {m.player.player_id}",
            jersey_number=target.jersey_number if is_focus else None,
            possession_s=possession.player_possession_s(m.player.player_id),
            touches=possession.player_touches(m.player.player_id),
            ratings=self.rating_model.rate(m.kinematics, counts, assessment),
            counts=counts,
            events=events or [],
            assessment=assessment,
        )
        if is_focus:
            report.event_positions = [(e, self._event_position(m.series, e)) for e in report.events]
        return report

    def _event_position(self, series: PositionSeries, event: MatchEvent) -> np.ndarray | None:
        frame = self.video.seconds_to_frame(event.timestamp_s)
        return series.position_at(frame, int(_EVENT_POSITION_TOLERANCE_S * self.video.fps))

    @staticmethod
    def _report_caveats(target: AnalysisTarget, possession: PossessionTimeline, share: dict[int, float]) -> list[str]:
        caveats = []
        if not target.is_player_mode:
            caveats.append(
                "In team mode, AI events are counted for the team as a whole, so each player's SHO / PAS / DRI / DEF "
                "are estimates; PAC and PHY are measured per player from tracking."
            )
        # team_by_frame carries the last team forward while the ball is in flight, so only frames with a player
        # actually at the ball count as evidence
        controlled_s = sum(1 for c in possession.controller_by_frame.values() if c is not None) * possession.frame_seconds
        clip_s = len(possession.controller_by_frame) * possession.frame_seconds
        if share and (controlled_s < _MIN_POSSESSION_SAMPLE_S or len(share) < 2):
            caveats.append(
                f"Possession rests on {controlled_s:.0f} s of clear ball control out of a {clip_s:.0f} s clip"
                + (", and only one team was seen in control" if len(share) < 2 else "")
                + ": the share is indicative, not a full-match figure."
            )
        return caveats

    @staticmethod
    def _caveats(geometry_mode: str, gemini: GeminiMatchAnalysis | None, gemini_status: str) -> list[str]:
        caveats = []
        if geometry_mode == "pitch_keypoints":
            caveats.append(
                "Positions use automatic pitch calibration from detected pitch landmarks; frames where too few "
                "landmarks were visible (close-ups, replays) are excluded from distance and maps."
            )
        if geometry_mode == "pose_scale":
            caveats.append(
                "Distances and speeds use pose-height scaling (no pitch calibration), accurate to roughly ±15%. "
                "Positions on maps are camera-relative, not absolute pitch coordinates."
            )
        caveats.append(
            "Physical metrics only cover time the player was on screen; broadcast cameras follow the ball, "
            "so off-ball running is under-counted."
        )
        if gemini is None:
            caveats.append("AI event analysis was unavailable for this run; technical attributes are neutral estimates.")
        elif gemini.caveats:
            caveats.append(f"AI analyst: {gemini.caveats}")
        return caveats
