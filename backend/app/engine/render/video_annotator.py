from dataclasses import dataclass, field

import cv2
import numpy as np

from app.core.app_config import RenderingConfig
from app.engine.domain import keypoints as kp
from app.engine.domain.models import BallObservation, PlayerObservation
from app.engine.render.palette import (
    BALL_COLOR,
    BGR,
    FOCUS_COLOR,
    PANEL_COLOR,
    TEXT_COLOR,
    ensure_visible,
    readable_text_color,
)

_FONT = cv2.FONT_HERSHEY_DUPLEX


@dataclass
class DrawnPlayer:
    player_id: int
    observation: PlayerObservation
    color: BGR
    emphasis: str  # "focus" | "team" | "other"


@dataclass
class HudStats:
    title: str
    clock_s: float
    possession: list[tuple[str, BGR, float]] = field(default_factory=list)
    lines: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class FrameOverlay:
    players: list[DrawnPlayer]
    ball: BallObservation | None
    controller_id: int | None
    focus_label: str | None
    focus_trail: list[np.ndarray]
    hud: HudStats
    minimap: np.ndarray | None = None


class VideoAnnotator:
    """Broadcast-style overlay: pose skeletons, kit-coloured ellipses, focus highlight, ball marker, HUD, minimap."""

    def __init__(self, config: RenderingConfig, min_keypoint_conf: float):
        self.config = config
        self.min_keypoint_conf = min_keypoint_conf

    def draw(self, frame: np.ndarray, overlay: FrameOverlay) -> np.ndarray:
        canvas = frame.copy()
        glow = np.zeros_like(canvas)

        for player in sorted(overlay.players, key=lambda p: p.emphasis == "focus"):
            self._draw_player(canvas, glow, player, overlay.controller_id == player.player_id)

        if overlay.focus_trail:
            self._draw_trail(canvas, overlay.focus_trail)
        canvas = cv2.addWeighted(canvas, 1.0, cv2.GaussianBlur(glow, (0, 0), 6), 0.9, 0)

        focus = next((p for p in overlay.players if p.emphasis == "focus"), None)
        if focus is not None and overlay.focus_label:
            self._draw_tag(canvas, focus.observation, overlay.focus_label)
        if overlay.ball is not None:
            self._draw_ball(canvas, overlay.ball)
        if self.config.hud:
            self._draw_hud(canvas, overlay.hud)
        if overlay.minimap is not None:
            self._paste_minimap(canvas, overlay.minimap)
        return canvas

    def _draw_player(self, canvas: np.ndarray, glow: np.ndarray, player: DrawnPlayer, has_ball: bool) -> None:
        obs = player.observation
        color = ensure_visible(player.color)
        x0, _, x1, y1 = obs.bbox
        foot = (int((x0 + x1) / 2), int(y1))
        width = max(int((x1 - x0) * 0.6), 8)

        if player.emphasis == "focus":
            cv2.ellipse(glow, foot, (width + 6, int(0.35 * width) + 4), 0, 0, 360, FOCUS_COLOR, 6, cv2.LINE_AA)
            self._draw_skeleton(glow, obs, FOCUS_COLOR, 5)
            self._draw_skeleton(canvas, obs, FOCUS_COLOR, 2)
            cv2.ellipse(canvas, foot, (width, int(0.35 * width)), 0, -45, 235, FOCUS_COLOR, 3, cv2.LINE_AA)
        else:
            thickness = 2 if player.emphasis == "team" else 1
            if self.config.skeleton_all_players:
                self._draw_skeleton(canvas, obs, color, thickness)
            cv2.ellipse(canvas, foot, (width, int(0.35 * width)), 0, -45, 235, color, thickness + 1, cv2.LINE_AA)

        if self.config.label_track_ids and player.emphasis != "other":
            label = str(player.player_id)
            (tw, th), _ = cv2.getTextSize(label, _FONT, 0.4, 1)
            top_left = (foot[0] - tw // 2 - 3, foot[1] + int(0.35 * width) + 2)
            cv2.rectangle(canvas, top_left, (top_left[0] + tw + 6, top_left[1] + th + 6), color, -1)
            cv2.putText(canvas, label, (top_left[0] + 3, top_left[1] + th + 2), _FONT, 0.4, readable_text_color(color), 1, cv2.LINE_AA)

        if has_ball:
            apex = (int((x0 + x1) / 2), int(obs.bbox[1]) - 6)
            self._triangle(canvas, apex, (0, 0, 255))

    def _draw_skeleton(self, canvas: np.ndarray, obs: PlayerObservation, color: BGR, thickness: int) -> None:
        points = obs.keypoints
        for a, b in kp.SKELETON_EDGES:
            if points[a, 2] >= self.min_keypoint_conf and points[b, 2] >= self.min_keypoint_conf:
                cv2.line(
                    canvas,
                    (int(points[a, 0]), int(points[a, 1])),
                    (int(points[b, 0]), int(points[b, 1])),
                    color,
                    thickness,
                    cv2.LINE_AA,
                )
        for x, y, c in points[5:]:
            if c >= self.min_keypoint_conf:
                cv2.circle(canvas, (int(x), int(y)), max(thickness, 2), color, -1, cv2.LINE_AA)

    def _draw_trail(self, canvas: np.ndarray, trail: list[np.ndarray]) -> None:
        for i in range(1, len(trail)):
            alpha = i / len(trail)
            color = tuple(int(c * alpha) for c in FOCUS_COLOR)
            cv2.line(canvas, tuple(trail[i - 1].astype(int)), tuple(trail[i].astype(int)), color, 1 + int(3 * alpha), cv2.LINE_AA)

    def _draw_tag(self, canvas: np.ndarray, obs: PlayerObservation, text: str) -> None:
        (tw, th), _ = cv2.getTextSize(text, _FONT, 0.55, 1)
        cx = int((obs.bbox[0] + obs.bbox[2]) / 2)
        top = int(obs.bbox[1]) - 34
        x0 = int(np.clip(cx - tw // 2 - 8, 0, canvas.shape[1] - tw - 16))
        y0 = max(top, 0)
        cv2.rectangle(canvas, (x0, y0), (x0 + tw + 16, y0 + th + 12), FOCUS_COLOR, -1)
        cv2.putText(canvas, text, (x0 + 8, y0 + th + 5), _FONT, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    def _draw_ball(self, canvas: np.ndarray, ball: BallObservation) -> None:
        cx, cy = int(ball.center[0]), int(ball.center[1])
        self._triangle(canvas, (cx, cy - 10), BALL_COLOR)

    @staticmethod
    def _triangle(canvas: np.ndarray, apex: tuple[int, int], color: BGR) -> None:
        x, y = apex
        points = np.array([[x, y], [x - 8, y - 16], [x + 8, y - 16]], dtype=np.int32)
        cv2.fillPoly(canvas, [points], color, cv2.LINE_AA)
        cv2.polylines(canvas, [points], True, (0, 0, 0), 1, cv2.LINE_AA)

    def _draw_hud(self, canvas: np.ndarray, hud: HudStats) -> None:
        width = 330
        height = 74 + 26 * len(hud.lines) + (34 if hud.possession else 0)
        x0, y0 = 16, 16
        region = canvas[y0: y0 + height, x0: x0 + width]
        panel = np.full_like(region, PANEL_COLOR)
        canvas[y0: y0 + height, x0: x0 + width] = cv2.addWeighted(region, 0.3, panel, 0.7, 0)
        cv2.rectangle(canvas, (x0, y0), (x0 + 5, y0 + height), FOCUS_COLOR, -1)

        cv2.putText(canvas, hud.title[:26], (x0 + 16, y0 + 28), _FONT, 0.65, TEXT_COLOR, 1, cv2.LINE_AA)
        clock = f"{int(hud.clock_s // 60):02d}:{int(hud.clock_s % 60):02d}"
        cv2.putText(canvas, clock, (x0 + width - 70, y0 + 28), _FONT, 0.6, FOCUS_COLOR, 1, cv2.LINE_AA)

        y = y0 + 56
        if hud.possession:
            bar_x, bar_w = x0 + 16, width - 32
            cursor = bar_x
            for i, (_, color, share) in enumerate(hud.possession):
                end = bar_x + bar_w if i == len(hud.possession) - 1 else cursor + int(bar_w * share)
                cv2.rectangle(canvas, (cursor, y - 12), (end, y + 8), ensure_visible(color), -1)
                if end - cursor >= 40:
                    cv2.putText(canvas, f"{share * 100:.0f}%", (cursor + 6, y + 4), _FONT, 0.45, readable_text_color(ensure_visible(color)), 1, cv2.LINE_AA)
                cursor = end
            cv2.putText(canvas, "POSSESSION", (bar_x, y + 26), _FONT, 0.38, (200, 200, 200), 1, cv2.LINE_AA)
            y += 50
        for label, value in hud.lines:
            cv2.putText(canvas, label, (x0 + 16, y), _FONT, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
            cv2.putText(canvas, value, (x0 + 180, y), _FONT, 0.55, TEXT_COLOR, 1, cv2.LINE_AA)
            y += 26

    @staticmethod
    def _paste_minimap(canvas: np.ndarray, minimap: np.ndarray) -> None:
        h, w = minimap.shape[:2]
        y0, x0 = canvas.shape[0] - h - 16, canvas.shape[1] - w - 16
        if y0 < 0 or x0 < 0:
            return
        canvas[y0: y0 + h, x0: x0 + w] = cv2.addWeighted(canvas[y0: y0 + h, x0: x0 + w], 0.15, minimap, 0.85, 0)
