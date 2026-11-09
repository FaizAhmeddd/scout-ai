from pathlib import Path

import numpy as np
import yaml

from app.core.app_config import PoseConfig, ReIdConfig
from app.engine.detection.model_loader import load_yolo, resolve_device
from app.engine.detection.reid_embedder import reid_model_path
from app.engine.domain.models import PlayerObservation

PERSON_CLASS_ID = 0


def resolve_tracker_config(tracker_config: Path, reid: ReIdConfig, models_dir: Path, runtime_dir: Path) -> Path:
    """Writes a runtime copy of the tracker YAML with an absolute ReID model path and the ReID switch applied."""
    settings = yaml.safe_load(tracker_config.read_text(encoding="utf-8"))
    if "with_reid" in settings:
        settings["with_reid"] = bool(reid.enabled and settings.get("with_reid"))
        if settings["with_reid"]:
            settings["model"] = str(reid_model_path(reid, models_dir))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    resolved = runtime_dir / tracker_config.name
    resolved.write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
    return resolved


class PoseTracker:
    """YOLO26 pose estimation + multi-object tracking: box, persistent track id and 17 keypoints per person.

    Used when `detector.type: pose`. The tracker (TrackTrack by default) associates detections with motion,
    camera-motion compensation and YOLO26 ReID appearance embeddings, so IDs survive crossings and occlusions.
    """

    def __init__(self, config: PoseConfig, tracker_config: Path, reid: ReIdConfig, models_dir: Path, runtime_dir: Path):
        self.config = config
        self.tracker_config = resolve_tracker_config(tracker_config, reid, models_dir, runtime_dir)
        self.model = load_yolo(config.model, models_dir)
        self.device = resolve_device(config.device)
        self.half = config.half and self.device != "cpu"

    def track(self, frame: np.ndarray, frame_idx: int) -> list[PlayerObservation]:
        result = self.model.track(
            frame,
            persist=True,
            tracker=str(self.tracker_config),
            conf=self.config.conf,
            iou=self.config.iou,
            imgsz=self.config.imgsz,
            device=self.device,
            quantize=16 if self.half else None,
            classes=[PERSON_CLASS_ID],
            verbose=False,
        )[0]

        if result.boxes is None or result.boxes.id is None or result.keypoints is None:
            return []

        boxes = result.boxes.xyxy.cpu().numpy().astype(np.float32)
        track_ids = result.boxes.id.int().cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        keypoints = result.keypoints.data.cpu().numpy().astype(np.float32)

        observations = []
        for box, track_id, confidence, kpts in zip(boxes, track_ids, confidences, keypoints):
            if box[3] - box[1] < self.config.min_box_height_px:
                continue
            observations.append(
                PlayerObservation(
                    frame_idx=frame_idx,
                    track_id=int(track_id),
                    bbox=box,
                    keypoints=kpts,
                    confidence=float(confidence),
                )
            )
        return observations
