from pathlib import Path

import numpy as np

from app.core.app_config import DetectorConfig, PoseConfig
from app.engine.detection.model_loader import load_yolo, resolve_device

NUM_KEYPOINTS = 17


class CropPoseEstimator:
    """Top-down pose: YOLO26 pose runs on each detected player's crop instead of the whole frame.

    A distant player is ~40-80 px tall in a 1080p broadcast; on the full frame the pose model misses many of them,
    while a padded crop upscaled to `pose_crop_imgsz` gives every detected player a skeleton.
    """

    def __init__(self, detector: DetectorConfig, pose: PoseConfig, models_dir: Path):
        self.detector = detector
        self.model = load_yolo(pose.model, models_dir)
        self.device = resolve_device(pose.device)
        self.half = pose.half and self.device != "cpu"

    def estimate(self, frame: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        """Returns (N, 17, 3) keypoints (x, y, confidence) in frame coordinates; zero confidence where none found."""
        keypoints = np.zeros((len(boxes), NUM_KEYPOINTS, 3), dtype=np.float32)
        if len(boxes) == 0:
            return keypoints

        crops, origins, inner_boxes = [], [], []
        h, w = frame.shape[:2]
        for box in boxes:
            x0, y0, x1, y1 = self._padded(box, w, h)
            crops.append(frame[y0:y1, x0:x1])
            origins.append((x0, y0))
            inner_boxes.append(box - np.array([x0, y0, x0, y0], dtype=np.float32))

        batch = self.detector.pose_batch_size
        for start in range(0, len(crops), batch):
            results = self.model.predict(
                crops[start:start + batch],
                imgsz=self.detector.pose_crop_imgsz,
                conf=0.1,
                device=self.device,
                quantize=16 if self.half else None,
                verbose=False,
            )
            for offset, result in enumerate(results):
                i = start + offset
                person = self._best_person(result, inner_boxes[i])
                if person is not None:
                    person[:, 0] += origins[i][0]
                    person[:, 1] += origins[i][1]
                    keypoints[i] = person
        return keypoints

    def _padded(self, box: np.ndarray, w: int, h: int) -> tuple[int, int, int, int]:
        bw, bh = box[2] - box[0], box[3] - box[1]
        mx, my = bw * self.detector.pose_crop_margin, bh * self.detector.pose_crop_margin
        x0, y0 = int(max(box[0] - mx, 0)), int(max(box[1] - my, 0))
        x1, y1 = int(min(box[2] + mx, w)), int(min(box[3] + my, h))
        return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)

    @staticmethod
    def _best_person(result, target: np.ndarray) -> np.ndarray | None:
        """The pose whose box overlaps the detected player most (a crop can also contain a team-mate or opponent)."""
        if result.boxes is None or len(result.boxes) == 0 or result.keypoints is None:
            return None
        boxes = result.boxes.xyxy.cpu().numpy()
        ix0, iy0 = np.maximum(boxes[:, 0], target[0]), np.maximum(boxes[:, 1], target[1])
        ix1, iy1 = np.minimum(boxes[:, 2], target[2]), np.minimum(boxes[:, 3], target[3])
        inter = np.clip(ix1 - ix0, 0, None) * np.clip(iy1 - iy0, 0, None)
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        target_area = (target[2] - target[0]) * (target[3] - target[1])
        iou = inter / np.maximum(areas + target_area - inter, 1e-6)
        best = int(np.argmax(iou))
        if iou[best] < 0.3:
            return None
        return result.keypoints.data[best].cpu().numpy().astype(np.float32)
