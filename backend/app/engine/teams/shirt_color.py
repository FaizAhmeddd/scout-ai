import cv2
import numpy as np

from app.engine.domain import keypoints as kp
from app.engine.domain.models import PlayerObservation
from app.engine.tracking.pitch_presence import grass_mask

_MIN_PIXELS = 25
_TORSO_SHRINK = 0.2
# Box-relative shirt region used when shoulders/hips are not confidently detected.
_FALLBACK_X = (0.3, 0.7)
_FALLBACK_Y = (0.18, 0.45)

# Histogram layout: 3 achromatic bins (black / grey / white) + 12 hues x 2 saturation levels.
_LOW_SATURATION = 50
_HIGH_SATURATION = 150
_HUE_BINS = 12
SHIRT_HISTOGRAM_BINS = 3 + _HUE_BINS * 2


class ShirtColorExtractor:
    """Describes a player's shirt from the shoulder-hip polygon (grass removed).

    Produces a colour histogram for team clustering — robust to shirt numbers, sponsor logos and
    contrasting bands, which skew a single average colour — plus a median CIE Lab colour for display.
    """

    def __init__(self, min_keypoint_conf: float):
        self.min_keypoint_conf = min_keypoint_conf

    def describe(self, frame: np.ndarray, obs: PlayerObservation) -> tuple[np.ndarray, np.ndarray] | None:
        pixels = self._shirt_pixels(frame, obs)
        if pixels is None:
            return None
        return self._median_lab(pixels), self._histogram(pixels)

    def _shirt_pixels(self, frame: np.ndarray, obs: PlayerObservation) -> np.ndarray | None:
        polygon = self._torso_polygon(obs)
        x0, y0 = np.floor(polygon.min(axis=0)).astype(int)
        x1, y1 = np.ceil(polygon.max(axis=0)).astype(int)
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
        if x1 - x0 < 3 or y1 - y0 < 3:
            return None

        crop = frame[y0:y1, x0:x1]
        mask = np.zeros(crop.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [np.round(polygon - [x0, y0]).astype(np.int32)], 255)
        mask &= ~grass_mask(crop)
        pixels = crop[mask > 0]
        return pixels if len(pixels) >= _MIN_PIXELS else None

    @staticmethod
    def _median_lab(pixels: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(pixels.reshape(-1, 1, 3).astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)
        return np.median(lab.reshape(-1, 3), axis=0).astype(np.float32)

    @staticmethod
    def _histogram(pixels: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int32)
        hue, sat, val = hsv[:, 0], hsv[:, 1], hsv[:, 2]
        achromatic = sat < _LOW_SATURATION
        bins = np.where(
            achromatic,
            np.digitize(val, [70, 170]),
            3 + (hue * _HUE_BINS // 180) * 2 + (sat >= _HIGH_SATURATION),
        )
        hist = np.bincount(bins, minlength=SHIRT_HISTOGRAM_BINS).astype(np.float32)
        return hist / hist.sum()

    def _torso_polygon(self, obs: PlayerObservation) -> np.ndarray:
        points = [obs.keypoint(i, self.min_keypoint_conf) for i in kp.TORSO_POLYGON]
        if all(p is not None for p in points):
            polygon = np.array(points, dtype=np.float32)
            centroid = polygon.mean(axis=0)
            polygon = centroid + (polygon - centroid) * (1 - _TORSO_SHRINK)
            if cv2.contourArea(polygon) > 30:
                return polygon
        x0, y0, x1, y1 = obs.bbox
        bw, bh = x1 - x0, y1 - y0
        return np.array(
            [
                [x0 + bw * _FALLBACK_X[0], y0 + bh * _FALLBACK_Y[0]],
                [x0 + bw * _FALLBACK_X[1], y0 + bh * _FALLBACK_Y[0]],
                [x0 + bw * _FALLBACK_X[1], y0 + bh * _FALLBACK_Y[1]],
                [x0 + bw * _FALLBACK_X[0], y0 + bh * _FALLBACK_Y[1]],
            ],
            dtype=np.float32,
        )
