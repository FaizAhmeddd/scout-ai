from pathlib import Path

import numpy as np
from ultralytics.engine.results import Boxes
from ultralytics.trackers.track import TRACKER_MAP
from ultralytics.utils import YAML, IterableSimpleNamespace

from app.core.app_config import DetectorConfig, PoseConfig, ReIdConfig
from app.engine.detection.crop_pose import CropPoseEstimator
from app.engine.detection.model_loader import resolve_device
from app.engine.detection.pose_tracker import resolve_tracker_config
from app.engine.detection.rfdetr_detector import RfDetrFootballDetector
from app.engine.domain.models import BallObservation, PlayerObservation


class FootballTracker:
    """Football detector -> multi-object tracker (with ReID) -> top-down pose on every tracked player.

    Same output as PoseTracker (box, persistent track id, 17 keypoints per person), plus each person's role
    (player / goalkeeper / referee) and the detector's ball candidates for the frame.
    """

    def __init__(
        self,
        detector: DetectorConfig,
        pose: PoseConfig,
        tracker_config: Path,
        reid: ReIdConfig,
        models_dir: Path,
        runtime_dir: Path,
    ):
        self.config = detector
        self.min_box_height_px = pose.min_box_height_px
        self.detector = RfDetrFootballDetector(detector, models_dir, pose.device, pose.half)
        self.pose = CropPoseEstimator(detector, pose, models_dir)
        resolved = resolve_tracker_config(tracker_config, reid, models_dir, runtime_dir)
        settings = IterableSimpleNamespace(**YAML.load(resolved))
        settings.device = resolve_device(pose.device)
        self.tracker = TRACKER_MAP[settings.tracker_type](args=settings)
        self.last_balls: list[BallObservation] = []

    def track(self, frame: np.ndarray, frame_idx: int) -> list[PlayerObservation]:
        detections = self.detector.detect(frame, frame_idx)
        self.last_balls = detections.balls if self.config.ball_candidates else []
        if len(detections.boxes) == 0:
            self.tracker.update(Boxes(np.zeros((0, 6), dtype=np.float32), frame.shape[:2]), frame)
            return []

        data = np.column_stack([detections.boxes, detections.confidences, detections.role_ids]).astype(np.float32)
        tracked = self.tracker.update(Boxes(data, frame.shape[:2]), frame)
        if len(tracked) == 0:
            return []

        # rows: x1, y1, x2, y2, track_id, score, cls, detection index. The detector's own box is kept (not the
        # Kalman-smoothed one) so keypoints, shirt crops and foot positions all come from the same pixels.
        det_idx = tracked[:, -1].astype(int)
        boxes = detections.boxes[det_idx]
        keep = boxes[:, 3] - boxes[:, 1] >= self.min_box_height_px
        tracked, det_idx, boxes = tracked[keep], det_idx[keep], boxes[keep]
        keypoints = self.pose.estimate(frame, boxes)

        return [
            PlayerObservation(
                frame_idx=frame_idx,
                track_id=int(row[4]),
                bbox=box.astype(np.float32),
                keypoints=kpts,
                confidence=float(detections.confidences[i]),
                role=detections.roles[i],
            )
            for row, i, box, kpts in zip(tracked, det_idx, boxes, keypoints)
        ]
