import logging

import cv2
import numpy as np

from app.core.app_config import CameraMotionConfig
from app.engine.domain.models import CameraMotion

logger = logging.getLogger(__name__)

# Broadcast overlays (scoreboard, tickers) are static and would anchor the estimate, so mask the bands they live in.
_TOP_OVERLAY_FRACTION = 0.12
_BOTTOM_OVERLAY_FRACTION = 0.10
_BOX_PADDING_PX = 6
_MIN_TRACKED_POINTS = 12


class CameraMotionEstimator:
    """Estimates per-frame camera pan/zoom with Lucas-Kanade optical flow on background features.

    Each frame gets a similarity transform into the coordinates of the first frame of its shot, so a
    player standing still has a constant stabilised position even while the broadcast camera pans.
    """

    def __init__(self, config: CameraMotionConfig):
        self.config = config
        self._motion = CameraMotion()
        self._prev_gray: np.ndarray | None = None
        self._prev_mask: np.ndarray | None = None
        self._cumulative = np.eye(3, dtype=np.float64)

    def update(self, frame_idx: int, frame: np.ndarray, player_boxes: list[np.ndarray]) -> None:
        if not self.config.enabled:
            self._motion.to_reference[frame_idx] = np.eye(3)
            return

        scale = self.config.downscale
        gray = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)
        mask = self._background_mask(gray.shape, player_boxes, scale)

        if self._prev_gray is None:
            self._cumulative = np.eye(3)
        else:
            step = self._estimate_step(self._prev_gray, self._prev_mask, gray, scale)
            if step is None:
                self._motion.scene_cuts.add(frame_idx)
                self._cumulative = np.eye(3)
            else:
                self._cumulative = self._cumulative @ step

        self._motion.to_reference[frame_idx] = self._cumulative.copy()
        self._prev_gray, self._prev_mask = gray, mask

    def result(self) -> CameraMotion:
        logger.info("Camera motion: %d scene cuts detected", len(self._motion.scene_cuts))
        return self._motion

    def _estimate_step(
        self, prev_gray: np.ndarray, prev_mask: np.ndarray, gray: np.ndarray, scale: float
    ) -> np.ndarray | None:
        """Returns the 3x3 transform mapping current-frame pixels to previous-frame pixels, or None on a cut."""
        prev_pts = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=self.config.max_corners,
            qualityLevel=self.config.quality_level,
            minDistance=self.config.min_distance,
            mask=prev_mask,
        )
        if prev_pts is None or len(prev_pts) < _MIN_TRACKED_POINTS:
            return np.eye(3)

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_pts, None)
        ok = status.reshape(-1) == 1
        if ok.sum() < _MIN_TRACKED_POINTS:
            return None

        matrix, inliers = cv2.estimateAffinePartial2D(
            next_pts[ok], prev_pts[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0
        )
        if matrix is None or inliers is None or inliers.mean() < self.config.min_inlier_ratio:
            return None

        step = np.eye(3)
        step[:2, :2] = matrix[:, :2]
        step[:2, 2] = matrix[:, 2] / scale
        return step

    @staticmethod
    def _background_mask(shape: tuple[int, int], boxes: list[np.ndarray], scale: float) -> np.ndarray:
        h, w = shape
        mask = np.full((h, w), 255, dtype=np.uint8)
        mask[: int(h * _TOP_OVERLAY_FRACTION)] = 0
        mask[h - int(h * _BOTTOM_OVERLAY_FRACTION):] = 0
        for box in boxes:
            x0, y0, x1, y1 = (box * scale).astype(int)
            mask[
                max(y0 - _BOX_PADDING_PX, 0): y1 + _BOX_PADDING_PX,
                max(x0 - _BOX_PADDING_PX, 0): x1 + _BOX_PADDING_PX,
            ] = 0
        return mask
