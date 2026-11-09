from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from app.core.app_config import PitchConfig
from app.engine.detection.model_loader import resolve_device
from app.engine.geometry.pitch_model import pitch_keypoints

_RANSAC_THRESHOLD_M = 1.0


class PitchKeypointDetector:
    """Automatic per-frame pitch calibration from Roboflow's 32-keypoint football-pitch model.

    Detected pitch landmarks (corners, box corners, centre circle, penalty spots) are matched to their
    real-world positions, giving an image->pitch homography for every frame without manual clicking.
    """

    def __init__(self, config: PitchConfig, models_dir: Path, device_preference: str, half: bool,
                 pitch_length_m: float, pitch_width_m: float):
        weights = models_dir / config.model
        if not weights.exists():
            raise FileNotFoundError(
                f"Pitch model not found at {weights}. Run `uv run python scripts/download_models.py`."
            )
        self.config = config
        self.model = YOLO(str(weights))
        self.device = resolve_device(device_preference)
        self.half = half and self.device != "cpu"
        self.pitch_points = pitch_keypoints(pitch_length_m, pitch_width_m)

    def homography(self, frame: np.ndarray) -> np.ndarray | None:
        result = self.model.predict(
            frame, conf=self.config.conf, imgsz=self.config.imgsz, device=self.device, quantize=16 if self.half else None, verbose=False
        )[0]
        if result.keypoints is None or len(result.keypoints) == 0:
            return None

        best = int(result.boxes.conf.argmax()) if result.boxes is not None and len(result.boxes) else 0
        keypoints = result.keypoints.data[best].cpu().numpy()
        if len(keypoints) != len(self.pitch_points):
            return None

        visible = (keypoints[:, 2] >= self.config.keypoint_conf) & (keypoints[:, 0] > 1) & (keypoints[:, 1] > 1)
        if visible.sum() < self.config.min_keypoints:
            return None

        homography, inliers = cv2.findHomography(
            keypoints[visible, :2], self.pitch_points[visible], cv2.RANSAC, _RANSAC_THRESHOLD_M
        )
        if homography is None or inliers is None or inliers.sum() < self.config.min_keypoints:
            return None
        return homography
