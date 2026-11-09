import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn

from app.core.app_config import AppConfig
from app.engine.cache.stage_cache import StageCache
from app.engine.detection.ball_detector import BallDetector, BallTrajectoryBuilder
from app.engine.detection.football_tracker import FootballTracker
from app.engine.detection.pitch_detector import PitchKeypointDetector
from app.engine.detection.pose_tracker import PoseTracker
from app.engine.detection.reid_embedder import ReIdEmbedder
from app.engine.domain.models import (
    OTHER_TEAM,
    AnalysisTarget,
    BallObservation,
    PlayerObservation,
    PlayerTrack,
    TeamAssignment,
    TrackingResult,
)
from app.engine.fusion.rating_model import RatingModel
from app.engine.fusion.report_builder import MatchReport, PlayerMetrics, ReportBuilder
from app.engine.gemini.agentic_analyst import GeminiAgenticAnalyst
from app.engine.gemini.prompts import GeminiTargetContext
from app.engine.gemini.schemas import GeminiMatchAnalysis
from app.engine.geometry.view_transformer import ViewTransformer
from app.engine.interactive.target_selector import SelectionContext, TargetSelector
from app.engine.io.video_reader import VideoReader
from app.engine.metrics.ball_path import build_ball_path
from app.engine.metrics.kinematics import KinematicsAnalyzer
from app.engine.metrics.pose_metrics import PoseMetricsAnalyzer
from app.engine.metrics.possession import PossessionAnalyzer, PossessionTimeline
from app.engine.motion.camera_motion_estimator import CameraMotionEstimator
from app.engine.render.match_renderer import MatchVideoRenderer
from app.engine.render.minimap import MinimapRenderer
from app.engine.render.video_annotator import VideoAnnotator
from app.engine.reports.chart_factory import ChartFactory
from app.engine.reports.html_report import HtmlReportWriter
from app.engine.reports.player_card import PlayerCardRenderer
from app.engine.reports.serializer import report_to_dict
from app.engine.teams.shirt_color import ShirtColorExtractor
from app.engine.teams.team_classifier import TeamClassifier
from app.engine.tracking.pitch_presence import PitchPresenceFilter
from app.engine.tracking.thumbnails import ThumbnailCollector
from app.engine.tracking.track_stitcher import TrackStitcher

logger = logging.getLogger(__name__)

_TRACKING_CACHE_VERSION = "tracking-v6"
_PROGRESS_EVERY_FRAMES = 15

ProgressCallback = Callable[[str, float], None]
_VISIBLE_WINDOW_MERGE_S = 2.0
_VISIBLE_WINDOW_MIN_S = 1.0


@dataclass
class PreparedMatch:
    video_path: Path
    reader: VideoReader
    fingerprint: str
    tracking: TrackingResult
    teams: TeamAssignment
    players: list[PlayerTrack]
    selection: SelectionContext
    output_dir: Path


@dataclass
class AnalysisOutputs:
    output_dir: Path
    report: MatchReport
    report_html: Path
    metrics_json: Path
    annotated_video: Path | None
    charts: dict[str, Path]
    player_card: Path | None
    gemini_json: Path | None


class MatchAnalysisPipeline:
    """End-to-end engine: track -> teams -> identities -> target -> metrics -> Gemini -> fusion -> outputs.

    Usable from the CLI (interactive selector) and from the API (preset selector).
    """

    def __init__(
        self,
        config: AppConfig,
        gemini_api_key: str = "",
        console: Console | None = None,
        progress: ProgressCallback | None = None,
    ):
        self.config = config
        self.gemini_api_key = gemini_api_key
        self.console = console or Console()
        self.progress = progress
        self.cache = StageCache(config.resolve(config.paths.cache_dir))
        self.models_dir = config.resolve(config.paths.models_dir)
        self.min_kp = config.pose.min_keypoint_conf

    def run(
        self,
        video_path: Path,
        selector: TargetSelector,
        use_gemini: bool = True,
        render_video: bool = True,
    ) -> AnalysisOutputs:
        return self.analyze(self.prepare(video_path), selector, use_gemini, render_video)

    def prepare(self, video_path: Path, output_dir: Path | None = None) -> PreparedMatch:
        """Pass 1 (cached): tracking, team identification and identity repair — everything needed to pick a target."""
        video_path = Path(video_path).resolve()
        reader = VideoReader(video_path, self.config.video.frame_stride, self.config.video.max_seconds)
        fingerprint = StageCache.fingerprint_video(video_path)

        self._stage("1/7", "Player detection, pose tracking, ball and camera motion", "tracking")
        tracking = self._tracking(reader, fingerprint)

        self._stage("2/7", "Team identification and identity repair", "teams")
        on_pitch = self._presence_filter().keep_players(tracking.tracks, tracking.pitch_homographies)
        classifier = TeamClassifier(self.config.teams)
        classifier.fit(on_pitch)
        on_pitch = classifier.split_mixed_tracks(on_pitch)
        teams = classifier.assign(on_pitch)
        players = TrackStitcher(self.config.stitching, reader.info.fps, self.min_kp, self.config.reid).stitch(
            on_pitch, teams, tracking.camera
        )

        if output_dir is None:
            output_dir = self.config.resolve(self.config.paths.output_root) / f"{video_path.stem}_{datetime.now():%Y%m%d_%H%M%S}"
        output_dir.mkdir(parents=True, exist_ok=True)
        selection = SelectionContext(players, teams, reader.info.frame_stride / reader.info.fps, output_dir)
        return PreparedMatch(video_path, reader, fingerprint, tracking, teams, players, selection, output_dir)

    def analyze(
        self,
        prepared: PreparedMatch,
        selector: TargetSelector,
        use_gemini: bool = True,
        render_video: bool = True,
    ) -> AnalysisOutputs:
        """Pass 2: metrics, Gemini, fusion and rendering for the chosen team or player."""
        video_path, reader, fingerprint = prepared.video_path, prepared.reader, prepared.fingerprint
        tracking, teams, players, output_dir = prepared.tracking, prepared.teams, prepared.players, prepared.output_dir
        frame_seconds = prepared.selection.frame_seconds

        self._stage("3/7", "Choose what to analyse", "selection")
        target = selector.select(prepared.selection)
        self.console.print(f"[green]Target:[/green] {target.label} ({'player' if target.is_player_mode else 'team'} mode)")

        self._stage("4/7", "Physical, pose and possession metrics", "metrics")
        transformer = ViewTransformer(
            self.config.geometry, tracking.camera, reader.info, self.min_kp, self.config.kinematics.max_gap_seconds,
            pitch_homographies=tracking.pitch_homographies,
            processed_frames=tracking.processed_frames,
            pitch_config=self.config.pitch,
        )
        transformer.fit(players)
        metrics = self._player_metrics(players, transformer, frame_seconds, reader.info.fps)
        possession = PossessionAnalyzer(self.config.possession, self.min_kp, frame_seconds).analyze(
            players, tracking.balls, tracking.processed_frames
        )

        self._stage("5/7", "AI video analysis (passes, dribbles, duels...)", "gemini")
        gemini, gemini_status = self._gemini(
            video_path, fingerprint, reader, target, teams, players, use_gemini
        )
        gemini_json = None
        if gemini is not None:
            gemini_json = output_dir / "events.json"
            gemini_json.write_text(gemini.model_dump_json(indent=2), encoding="utf-8")

        self._stage("6/7", "Fusing metrics and computing ratings", "fusion")
        ball_path = build_ball_path(
            tracking.balls, transformer, possession, teams.colors_bgr, reader.info.fps,
            self.config.geometry.pitch_length_m, self.config.geometry.pitch_width_m,
        )
        report = ReportBuilder(RatingModel(), reader.info).build(
            target, teams, metrics, possession, gemini, gemini_status, transformer.mode, transformer.uses_pitch_coordinates,
            ball_path,
        )

        self._stage("7/7", "Rendering annotated video, graphs and report", "rendering")
        annotated = (
            self._render_video(reader, output_dir, target, players, teams, tracking.balls, possession, metrics, transformer)
            if render_video
            else None
        )
        self._notify("reporting", 0.0)
        charts, card = self._charts(report, output_dir)
        metrics_json = output_dir / "metrics.json"
        metrics_json.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")
        report_html = HtmlReportWriter().write(report, charts, card, annotated, output_dir / "report.html")

        return AnalysisOutputs(
            output_dir=output_dir,
            report=report,
            report_html=report_html,
            metrics_json=metrics_json,
            annotated_video=annotated,
            charts=charts,
            player_card=card,
            gemini_json=gemini_json,
        )

    # ------------------------------------------------------------------ stages

    def tracking_signature(self) -> str:
        """Identifies everything that shapes detected players and their numbering (tracking, teams, identities).

        Stored with a video's detected players; if it changes (e.g. a tracker upgrade), the stored player
        numbers no longer match what an analysis would see, so detection must be re-run.
        """
        return StageCache.make_key(
            *self._tracking_parts(), self.config.presence, self.config.teams, self.config.stitching
        )

    def _tracking_parts(self) -> tuple:
        return (
            _TRACKING_CACHE_VERSION, self.config.video, self.config.detector, self.config.pose, self.config.ball,
            self.config.pitch, self.config.camera_motion, self.config.geometry.pitch_length_m, self.config.geometry.pitch_width_m,
            self.config.presence.min_grass_fraction, self.config.reid,
            self.config.resolve(self._tracker_yaml()).read_text(encoding="utf-8"),
        )

    def _tracker_yaml(self) -> Path:
        return self.config.detector.tracker if self.config.detector.type == "rfdetr" else self.config.pose.tracker

    def _player_tracker(self) -> PoseTracker | FootballTracker:
        runtime_dir = self.config.resolve(self.config.paths.cache_dir) / "trackers"
        tracker_yaml = self.config.resolve(self._tracker_yaml())
        if self.config.detector.type == "rfdetr":
            return FootballTracker(
                self.config.detector, self.config.pose, tracker_yaml, self.config.reid, self.models_dir, runtime_dir
            )
        return PoseTracker(self.config.pose, tracker_yaml, self.config.reid, self.models_dir, runtime_dir)

    def _tracking(self, reader: VideoReader, fingerprint: str) -> TrackingResult:
        version, *settings = self._tracking_parts()
        key = StageCache.make_key(version, fingerprint, *settings)
        return self.cache.get_or_compute("tracking", key, lambda: self._run_tracking(reader))

    def _run_tracking(self, reader: VideoReader) -> TrackingResult:
        pose = self._player_tracker()
        reid = ReIdEmbedder(self.config.reid, self.models_dir, self.config.pose.device) if self.config.reid.enabled else None
        ball = BallDetector(self.config.ball, self.models_dir, self.config.pose.device, self.config.pose.half)
        camera = CameraMotionEstimator(self.config.camera_motion)
        shirts = ShirtColorExtractor(self.min_kp)
        presence = self._presence_filter()
        pitch = self._pitch_detector()
        thumbnails = ThumbnailCollector()

        tracks: dict[int, list[PlayerObservation]] = {}
        ball_candidates: dict[int, list[BallObservation]] = {}
        homographies: dict[int, np.ndarray] = {}
        processed: list[int] = []

        with self._progress() as progress:
            task = progress.add_task("Tracking", total=len(reader))
            for frame_idx, frame in reader.frames():
                observations = pose.track(frame, frame_idx)
                for obs in observations:
                    if (shirt := shirts.describe(frame, obs)) is not None:
                        obs.torso_color_lab, obs.torso_hist = shirt
                    obs.on_grass = presence.feet_on_grass(frame, obs)
                    tracks.setdefault(obs.track_id, []).append(obs)
                thumbnails.add_frame(frame, observations)
                if reid is not None and len(processed) % self.config.reid.sample_every_n_frames == 0:
                    reid.embed(frame, observations)
                candidates = ball.detect(frame, frame_idx) + getattr(pose, "last_balls", [])
                ball_candidates[frame_idx] = sorted(candidates, key=lambda b: b.confidence, reverse=True)
                camera.update(frame_idx, frame, [o.bbox for o in observations])
                if pitch is not None and len(processed) % self.config.pitch.every_n_frames == 0:
                    if (homography := pitch.homography(frame)) is not None:
                        homographies[frame_idx] = homography
                processed.append(frame_idx)
                progress.advance(task)
                if len(processed) % _PROGRESS_EVERY_FRAMES == 0:
                    self._notify("tracking", len(processed) / len(reader))

        camera_motion = camera.result()
        tracks = self._split_at_scene_cuts(tracks, camera_motion)
        balls = BallTrajectoryBuilder(self.config.ball, reader.info.frame_stride).build(ball_candidates, processed)
        logger.info(
            "Tracking done: %d raw tracks, ball in %d/%d frames, pitch calibrated in %d frames",
            len(tracks), len(balls), len(processed), len(homographies),
        )
        return TrackingResult(
            video=reader.info, processed_frames=processed, tracks=tracks, balls=balls, camera=camera_motion,
            pitch_homographies=homographies,
        )

    def _presence_filter(self) -> PitchPresenceFilter:
        geometry = self.config.geometry
        return PitchPresenceFilter(self.config.presence, geometry.pitch_length_m, geometry.pitch_width_m)

    def _pitch_detector(self) -> PitchKeypointDetector | None:
        if not self.config.pitch.enabled or self.config.geometry.mode == "pose_scale":
            return None
        try:
            return PitchKeypointDetector(
                self.config.pitch, self.models_dir, self.config.pose.device, self.config.pose.half,
                self.config.geometry.pitch_length_m, self.config.geometry.pitch_width_m,
            )
        except FileNotFoundError as exc:
            logger.warning("%s Falling back to pose-scale geometry.", exc)
            return None

    @staticmethod
    def _split_at_scene_cuts(tracks: dict[int, list[PlayerObservation]], camera) -> dict[int, list[PlayerObservation]]:
        """ByteTrack can carry an id across a broadcast cut; positions on either side are unrelated, so split."""
        if not camera.scene_cuts:
            return tracks
        next_id = max(tracks, default=0) + 1
        split_tracks = {}
        for tid, observations in tracks.items():
            by_segment: dict[int, list[PlayerObservation]] = {}
            for obs in observations:
                by_segment.setdefault(camera.segment_id(obs.frame_idx), []).append(obs)
            for i, (_, segment_obs) in enumerate(sorted(by_segment.items())):
                new_id = tid if i == 0 else next_id
                if i:
                    next_id += 1
                for obs in segment_obs:
                    obs.track_id = new_id
                split_tracks[new_id] = segment_obs
        return split_tracks

    def _player_metrics(
        self, players: list[PlayerTrack], transformer: ViewTransformer, frame_seconds: float, fps: float
    ) -> dict[int, PlayerMetrics]:
        kinematics = KinematicsAnalyzer(self.config.kinematics)
        pose = PoseMetricsAnalyzer(self.config.pose_metrics, self.min_kp)
        metrics = {}
        for player in players:
            if player.team_id == OTHER_TEAM:
                continue
            series = transformer.series(player)
            kin = kinematics.analyze(series)
            metrics[player.player_id] = PlayerMetrics(
                player=player,
                series=series,
                kinematics=kin,
                pose=pose.analyze(player, kin, fps),
                on_screen_s=len(player.observations) * frame_seconds,
            )
        return metrics

    def _gemini(
        self,
        video_path: Path,
        fingerprint: str,
        reader: VideoReader,
        target: AnalysisTarget,
        teams: TeamAssignment,
        players: list[PlayerTrack],
        use_gemini: bool,
    ) -> tuple[GeminiMatchAnalysis | None, str]:
        if not (use_gemini and self.config.gemini.enabled):
            return None, "disabled"
        if not self.gemini_api_key:
            self.console.print("[yellow]AI event analysis is not configured (API key missing in backend/.env) - skipping.[/yellow]")
            return None, "no API key"

        context = self._gemini_context(reader, target, teams, players)
        analyst = GeminiAgenticAnalyst(self.config.gemini, self.gemini_api_key, self.cache)
        with self.console.status("The AI analyst is watching the match (this can take a few minutes)..."):
            return analyst.analyze(video_path, fingerprint, context, self.config.video.max_seconds)

    def _gemini_context(
        self, reader: VideoReader, target: AnalysisTarget, teams: TeamAssignment, players: list[PlayerTrack]
    ) -> GeminiTargetContext:
        opponent = next((name for t, name in teams.color_names.items() if t != target.team_id), "unknown")
        context = GeminiTargetContext(
            mode="player" if target.is_player_mode else "team",
            team_color=teams.color_names[target.team_id],
            opponent_color=opponent,
            video_duration_s=reader.info.frame_count / reader.info.fps,
            jersey_number=target.jersey_number,
            player_label=target.label,
        )
        if target.is_player_mode:
            player = next(p for p in players if p.player_id == target.player_id)
            context.visible_windows = _visible_windows([o.frame_idx / reader.info.fps for o in player.observations])
            if player.thumbnail is not None:
                ok, jpeg = cv2.imencode(".jpg", player.thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 92])
                context.reference_image_jpeg = jpeg.tobytes() if ok else None
        return context

    def _render_video(self, reader, output_dir, target, players, teams, balls, possession: PossessionTimeline, metrics, transformer) -> Path:
        geometry = self.config.geometry
        minimap = (
            MinimapRenderer(geometry.pitch_length_m, geometry.pitch_width_m)
            if self.config.rendering.minimap and transformer.uses_pitch_coordinates
            else None
        )
        renderer = MatchVideoRenderer(VideoAnnotator(self.config.rendering, self.min_kp), self.config.rendering, minimap)
        with self._progress() as progress:
            task = progress.add_task("Rendering", total=len(reader))
            return renderer.render(
                reader, output_dir / "annotated.mp4", target, players, teams, balls, possession, metrics, transformer,
                on_frame=lambda: self._advance_render(progress, task, len(reader)),
            )

    def _charts(self, report: MatchReport, output_dir: Path) -> tuple[dict[str, Path], Path | None]:
        geometry = self.config.geometry
        factory = ChartFactory(
            output_dir / "charts", self.config.report.dpi, geometry.pitch_length_m, geometry.pitch_width_m,
            self.config.kinematics.speed_zones_kmh,
        )
        if report.focus_player is not None:
            card = PlayerCardRenderer(self.config.report.dpi).render(
                report.focus_player, report.focus_team.color_bgr, output_dir / "charts" / "player_card.png"
            )
            return factory.player_charts(report), card
        return factory.team_charts(report), None

    # ------------------------------------------------------------------ ui helpers

    def _stage(self, step: str, title: str, key: str) -> None:
        self.console.rule(f"[bold yellow]{step}[/bold yellow]  {title}")
        self._notify(key, 0.0)

    def _notify(self, stage: str, fraction: float) -> None:
        if self.progress is not None:
            self.progress(stage, min(max(fraction, 0.0), 1.0))

    def _advance_render(self, progress: Progress, task, total: int) -> None:
        progress.advance(task)
        done = progress.tasks[0].completed
        if done % _PROGRESS_EVERY_FRAMES == 0:
            self._notify("rendering", done / total)

    def _progress(self) -> Progress:
        return Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("frames"),
            TimeRemainingColumn(),
            console=self.console,
        )


def _visible_windows(seconds: list[float]) -> list[tuple[float, float]]:
    windows: list[list[float]] = []
    for s in sorted(seconds):
        if windows and s - windows[-1][1] <= _VISIBLE_WINDOW_MERGE_S:
            windows[-1][1] = s
        else:
            windows.append([s, s])
    return [(a, b) for a, b in windows if b - a >= _VISIBLE_WINDOW_MIN_S]
