import cv2
import numpy as np

from app.engine.render.palette import BGR, FOCUS_COLOR

_GRASS = (46, 110, 52)
_LINE = (235, 235, 235)


class MinimapRenderer:
    """Top-down pitch radar; only meaningful when positions are in real pitch coordinates."""

    def __init__(self, pitch_length_m: float, pitch_width_m: float, width_px: int = 300):
        self.length = pitch_length_m
        self.width = pitch_width_m
        self.scale = width_px / pitch_length_m
        self.size = (width_px, int(pitch_width_m * self.scale))
        self._base = self._draw_pitch()

    def render(self, dots: list[tuple[np.ndarray, BGR, bool]], ball: np.ndarray | None = None) -> np.ndarray:
        image = self._base.copy()
        for xy, color, is_focus in dots:
            point = self._to_px(xy)
            if point is None:
                continue
            if is_focus:
                cv2.circle(image, point, 8, FOCUS_COLOR, 2, cv2.LINE_AA)
            cv2.circle(image, point, 5, color, -1, cv2.LINE_AA)
            cv2.circle(image, point, 5, (0, 0, 0), 1, cv2.LINE_AA)
        if ball is not None and (point := self._to_px(ball)) is not None:
            cv2.circle(image, point, 3, (255, 255, 255), -1, cv2.LINE_AA)
        return image

    def _to_px(self, xy: np.ndarray) -> tuple[int, int] | None:
        x, y = float(xy[0]), float(xy[1])
        if not (-5 <= x <= self.length + 5 and -5 <= y <= self.width + 5):
            return None
        return int(np.clip(x, 0, self.length) * self.scale), int(np.clip(y, 0, self.width) * self.scale)

    def _draw_pitch(self) -> np.ndarray:
        w, h = self.size
        s = self.scale
        image = np.full((h, w, 3), _GRASS, dtype=np.uint8)
        cv2.rectangle(image, (0, 0), (w - 1, h - 1), _LINE, 1)
        cv2.line(image, (w // 2, 0), (w // 2, h), _LINE, 1)
        cv2.circle(image, (w // 2, h // 2), int(9.15 * s), _LINE, 1)
        box_w, box_h = int(16.5 * s), int(40.32 * s)
        top = (h - box_h) // 2
        cv2.rectangle(image, (0, top), (box_w, top + box_h), _LINE, 1)
        cv2.rectangle(image, (w - box_w, top), (w - 1, top + box_h), _LINE, 1)
        return image
