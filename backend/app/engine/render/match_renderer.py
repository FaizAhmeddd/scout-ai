from collections import deque
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.core.app_config import RenderingConfig
from app.engine.domain.models import OTHER_TEAM, AnalysisTarget, BallObservation, PlayerObservation, PlayerTrack, TeamAssignment
from app.engine.fusion.report_builder import PlayerMetrics
from app.engine.geometry.view_transformer import ViewTransformer
from app.engine.io.video_reader import VideoReader
from app.engine.io.video_writer import VideoWriter
from app.engine.metrics.possession import PossessionTimeline
from app.engine.render.minimap import MinimapRenderer
from app.engine.render.palette import BGR, OTHER_COLOR
from app.engine.render.video_annotator import DrawnPlayer, FrameOverlay, HudStats, VideoAnnotator


class MatchVideoRenderer:
    """Second pass over the video: draws every frame from the cached analysis and writes the annotated mp4."""

    def __init__(self, annotator: VideoAnnotator, config: RenderingConfig, minimap: MinimapRenderer | None):
        self.annotator = annotator
        self.config = config
        self.minimap = minimap

    def render(
        self,
        reader: VideoReader,
        output_path: Path,
        target: AnalysisTarget,
        players: list[PlayerTrack],
        teams: TeamAssignment,
        balls: dict[int, BallObservation],
        possession: PossessionTimeline,
        metrics: dict[int, PlayerMetrics],
        transformer: ViewTransformer,
        on_frame: Callable[[], None] | None = None,
    ) -> Path:
        by_frame: dict[int, list[tuple[PlayerTrack, PlayerObservation]]] = {}
        for player in players:
            for obs in player.observations:
                by_frame.setdefault(obs.frame_idx, []).append((player, obs))

        map_positions = self._map_positions(metrics) if self.minimap else {}
        focus_metrics = metrics.get(target.player_id) if target.is_player_mode else None
        self._running_top_speed = (
            np.maximum.accumulate(focus_metrics.kinematics.sustained_speed_kmh)
            if focus_metrics is not None and len(focus_metrics.kinematics.sustained_speed_kmh)
            else np.zeros(0)
        )
        team_metrics = [m for m in metrics.values() if m.player.team_id == target.team_id]
        trail: deque[tuple[int, np.ndarray]] = deque(maxlen=self.config.trail_length)
        possession_frames = {team: 0 for team in teams.color_names}
        focus_control_frames = 0
        fps = reader.info.fps

        info = reader.info
        with VideoWriter(output_path, info.effective_fps, (info.width, info.height), self.config.transcode_h264) as writer:
            for frame_idx, frame in reader.frames():
                seconds = frame_idx / fps
                team_now = possession.team_by_frame.get(frame_idx)
                if team_now is not None:
                    possession_frames[team_now] += 1
                if target.is_player_mode and possession.controller_by_frame.get(frame_idx) == target.player_id:
                    focus_control_frames += 1

                drawn = [
                    DrawnPlayer(p.player_id, obs, self._color(p, teams), self._emphasis(p, target))
                    for p, obs in by_frame.get(frame_idx, [])
                ]
                focus_obs = next((d.observation for d in drawn if d.emphasis == "focus"), None)
                if focus_obs is not None:
                    trail.append((frame_idx, transformer.camera.stabilize(frame_idx, focus_obs.foot_point(self.annotator.min_keypoint_conf))))

                overlay = FrameOverlay(
                    players=drawn,
                    ball=balls.get(frame_idx),
                    controller_id=possession.controller_by_frame.get(frame_idx),
                    focus_label=self._focus_label(target, focus_metrics, seconds) if focus_obs is not None else None,
                    focus_trail=self._trail_in_frame(trail, frame_idx, transformer),
                    hud=self._hud(
                        target, teams, possession_frames, focus_metrics, team_metrics,
                        focus_control_frames * possession.frame_seconds, seconds,
                        sum(1 for d in drawn if d.emphasis == "team"),
                    ),
                    minimap=self._minimap(frame_idx, map_positions, teams, target, balls, transformer),
                )
                writer.write(self.annotator.draw(frame, overlay))
                if on_frame:
                    on_frame()
        return output_path

    @staticmethod
    def _color(player: PlayerTrack, teams: TeamAssignment) -> BGR:
        return teams.colors_bgr.get(player.team_id, OTHER_COLOR) if player.team_id != OTHER_TEAM else OTHER_COLOR

    @staticmethod
    def _emphasis(player: PlayerTrack, target: AnalysisTarget) -> str:
        if target.is_player_mode and player.player_id == target.player_id:
            return "focus"
        return "team" if player.team_id == target.team_id else "other"

    @staticmethod
    def _focus_label(target: AnalysisTarget, metrics: PlayerMetrics | None, seconds: float) -> str:
        speed = metrics.kinematics.speed_at(seconds) if metrics else None
        return f"{target.label}  {speed:.1f} km/h" if speed is not None else target.label

    @staticmethod
    def _trail_in_frame(trail: deque, frame_idx: int, transformer: ViewTransformer) -> list[np.ndarray]:
        segment = transformer.camera.segment_id(frame_idx)
        return [
            transformer.camera.destabilize(frame_idx, point)
            for f, point in trail
            if transformer.camera.segment_id(f) == segment and frame_idx - f < 3 * transformer.video.fps
        ]

    def _hud(
        self,
        target: AnalysisTarget,
        teams: TeamAssignment,
        possession_frames: dict[int, int],
        focus: PlayerMetrics | None,
        team_metrics: list[PlayerMetrics],
        focus_control_s: float,
        seconds: float,
        team_on_screen: int,
    ) -> HudStats:
        total = sum(possession_frames.values())
        bar = [
            (teams.color_names[t], teams.colors_bgr[t], possession_frames[t] / total)
            for t in sorted(possession_frames)
        ] if total else []

        if focus is not None:
            kin = focus.kinematics
            last = int(np.searchsorted(kin.seconds, seconds, side="right")) - 1
            top = float(self._running_top_speed[last]) if last >= 0 else 0.0
            speed = kin.speed_at(seconds)
            lines = [
                ("SPEED", f"{speed:.1f} km/h" if speed is not None else "--"),
                ("DISTANCE", f"{kin.distance_until(seconds):.0f} m"),
                ("TOP SPEED", f"{top:.1f} km/h"),
                ("SPRINTS", str(sum(1 for s in kin.sprints if s.start_s <= seconds))),
                ("BALL CONTROL", f"{focus_control_s:.1f} s"),
            ]
        else:
            team_distance = sum(m.kinematics.distance_until(seconds) for m in team_metrics)
            lines = [
                ("TEAM DISTANCE", f"{team_distance / 1000:.2f} km"),
                ("ON SCREEN NOW", f"{team_on_screen} players"),
            ]
        return HudStats(title=target.label.upper(), clock_s=seconds, possession=bar, lines=lines)

    @staticmethod
    def _map_positions(metrics: dict[int, PlayerMetrics]) -> dict[int, list[tuple[PlayerTrack, np.ndarray]]]:
        positions: dict[int, list[tuple[PlayerTrack, np.ndarray]]] = {}
        for m in metrics.values():
            if not m.series.on_pitch:
                continue
            for frame, xy in zip(m.series.frames, m.series.xy_m):
                positions.setdefault(int(frame), []).append((m.player, xy))
        return positions

    def _minimap(
        self,
        frame_idx: int,
        map_positions: dict[int, list[tuple[PlayerTrack, np.ndarray]]],
        teams: TeamAssignment,
        target: AnalysisTarget,
        balls: dict[int, BallObservation],
        transformer: ViewTransformer,
    ) -> np.ndarray | None:
        if self.minimap is None or frame_idx not in map_positions:
            return None
        dots = [
            (xy, self._color(player, teams), target.is_player_mode and player.player_id == target.player_id)
            for player, xy in map_positions[frame_idx]
        ]
        ball = balls.get(frame_idx)
        return self.minimap.render(dots, transformer.project(frame_idx, ball.center) if ball else None)
