import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from app.core.app_config import DetectorConfig
from app.engine.detection.model_loader import resolve_device
from app.engine.domain.models import ROLE_GOALKEEPER, ROLE_PLAYER, ROLE_REFEREE, BallObservation

logger = logging.getLogger(__name__)

_PERSON_ROLES = (ROLE_PLAYER, ROLE_GOALKEEPER, ROLE_REFEREE)
_BALL = "ball"


@dataclass(slots=True)
class FootballDetections:
    """One frame of football-specific detections: people (with their role) and ball candidates."""

    boxes: np.ndarray  # (N, 4) xyxy of players, goalkeepers and referees
    confidences: np.ndarray  # (N,)
    roles: list[str]  # (N,) one of ROLE_PLAYER / ROLE_GOALKEEPER / ROLE_REFEREE
    balls: list[BallObservation]

    @property
    def role_ids(self) -> np.ndarray:
        return np.array([_PERSON_ROLES.index(r) for r in self.roles], dtype=np.float32)


class RfDetrFootballDetector:
    """RF-DETR fine-tuned on SoccerNet: detects players, goalkeepers, referees and the ball in one pass.

    Trained on broadcast football, it finds far more of the small, distant and partly occluded players than a
    generic person/pose model, and it tells referees and goalkeepers apart from outfield players.
    """

    def __init__(self, config: DetectorConfig, models_dir: Path, device_preference: str, half: bool):
        from rfdetr.variants import RFDETRLargeDeprecated  # heavy import: only when this detector is used

        checkpoint = models_dir / config.checkpoint
        if not checkpoint.exists():
            raise FileNotFoundError(
                f"Football detector checkpoint not found at {checkpoint} - run `uv run python scripts/download_models.py`"
            )
        self.config = config
        self.device = resolve_device(device_preference)
        self.half = half and self.device != "cpu"
        # The checkpoint is the legacy RF-DETR Large (DINOv2-base, patch size 14). RFDETR.from_checkpoint would pick
        # the newer Large (patch size 16) from its weights name, so the matching class is built explicitly. The file
        # stores its training arguments as a pickled namespace, so it needs full deserialisation; it is a file we
        # download explicitly (scripts/download_models.py), never user input.
        self.model = RFDETRLargeDeprecated(
            pretrain_weights=str(checkpoint), num_classes=len(config.class_names), device=self.device,
            trust_checkpoint=True,
        )
        mc = self.model.model_config
        self.block = mc.patch_size * mc.num_windows
        self.class_names = [name.lower() for name in config.class_names]
        self.min_threshold = min(config.threshold, config.ball_threshold)
        logger.info("Football detector loaded (%s, %s)", checkpoint.name, self.device)

    def detect(self, frame: np.ndarray, frame_idx: int) -> FootballDetections:
        rgb = np.ascontiguousarray(frame[:, :, ::-1])
        with self._autocast():
            detections = self.model.predict(rgb, threshold=self.min_threshold, shape=self._input_shape(frame))

        boxes, confidences, roles, balls = [], [], [], []
        for xyxy, confidence, class_id in zip(detections.xyxy, detections.confidence, detections.class_id):
            name = self.class_names[int(class_id)] if 0 <= int(class_id) < len(self.class_names) else None
            if name == _BALL:
                if confidence >= self.config.ball_threshold:
                    center = np.array([(xyxy[0] + xyxy[2]) / 2, (xyxy[1] + xyxy[3]) / 2], dtype=np.float32)
                    balls.append(BallObservation(frame_idx=frame_idx, center=center, confidence=float(confidence)))
            elif name in _PERSON_ROLES and confidence >= self.config.threshold:
                boxes.append(np.asarray(xyxy, dtype=np.float32))
                confidences.append(float(confidence))
                roles.append(name)

        return FootballDetections(
            boxes=np.stack(boxes) if boxes else np.zeros((0, 4), dtype=np.float32),
            confidences=np.array(confidences, dtype=np.float32),
            roles=roles,
            balls=sorted(balls, key=lambda b: b.confidence, reverse=True),
        )

    def _input_shape(self, frame: np.ndarray) -> tuple[int, int]:
        """(height, width) the model sees: the frame's aspect ratio, long side `resolution`, multiples of `block`.

        The checkpoint was trained at 560 px; running larger keeps distant, small players detectable.
        """
        h, w = frame.shape[:2]
        scale = self.config.resolution / max(h, w)
        snap = lambda size: max(self.block, round(size * scale / self.block) * self.block)  # noqa: E731
        return snap(h), snap(w)

    def _autocast(self):
        if self.half and self.device.startswith("cuda"):
            return torch.autocast("cuda", dtype=torch.float16)
        return contextlib.nullcontext()
