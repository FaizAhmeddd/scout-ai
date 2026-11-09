import logging
from pathlib import Path

import numpy as np

from app.core.app_config import BallConfig
from app.engine.detection.model_loader import load_yolo, resolve_device
from app.engine.domain.models import BallObservation

logger = logging.getLogger(__name__)


class BallDetector:
    """Detects ball candidates per frame. Candidate selection happens in BallTrajectoryBuilder."""

    def __init__(self, config: BallConfig, models_dir: Path, device_preference: str, half: bool):
        self.config = config
        weights = config.model
        if not (models_dir / config.model).exists() and not config.model.startswith("yolo"):
            logger.warning("Ball model %s not found in %s - using %s (run scripts/download_models.py)",
                           config.model, models_dir, config.fallback_model)
            weights = config.fallback_model
        self.model = load_yolo(weights, models_dir)
        self.device = resolve_device(device_preference)
        self.half = half and self.device != "cpu"
        wanted = {name.lower() for name in config.class_names}
        self.class_ids = [cid for cid, name in self.model.names.items() if name.lower() in wanted]
        if not self.class_ids:
            raise ValueError(f"Ball model {config.model} has none of the classes {config.class_names}")

    def detect(self, frame: np.ndarray, frame_idx: int) -> list[BallObservation]:
        result = self.model.predict(
            frame,
            conf=self.config.conf,
            imgsz=self.config.imgsz,
            device=self.device,
            quantize=16 if self.half else None,
            classes=self.class_ids,
            verbose=False,
        )[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []

        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        candidates = [
            BallObservation(
                frame_idx=frame_idx,
                center=np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2], dtype=np.float32),
                confidence=float(c),
            )
            for b, c in zip(boxes, confidences)
        ]
        return sorted(candidates, key=lambda obs: obs.confidence, reverse=True)


class BallTrajectoryBuilder:
    """Turns noisy per-frame candidates into one plausible ball trajectory, interpolating short gaps."""

    def __init__(self, config: BallConfig, frame_stride: int):
        self.config = config
        self.frame_stride = frame_stride

    def build(
        self, candidates: dict[int, list[BallObservation]], processed_frames: list[int]
    ) -> dict[int, BallObservation]:
        accepted = self._select_consistent(candidates, processed_frames)
        return self._interpolate(accepted, processed_frames)

    def _select_consistent(
        self, candidates: dict[int, list[BallObservation]], processed_frames: list[int]
    ) -> dict[int, BallObservation]:
        accepted: dict[int, BallObservation] = {}
        last: BallObservation | None = None
        max_gap_frames = self.config.max_interpolation_gap * self.frame_stride

        for frame_idx in processed_frames:
            options = candidates.get(frame_idx, [])
            if not options:
                continue
            if last is None or frame_idx - last.frame_idx > max_gap_frames:
                choice = options[0]
            else:
                reach = self.config.max_jump_px_per_frame * (frame_idx - last.frame_idx)
                in_reach = [o for o in options if np.linalg.norm(o.center - last.center) <= reach]
                if not in_reach:
                    continue
                choice = min(in_reach, key=lambda o: np.linalg.norm(o.center - last.center))
            accepted[frame_idx] = choice
            last = choice
        return accepted

    def _interpolate(
        self, accepted: dict[int, BallObservation], processed_frames: list[int]
    ) -> dict[int, BallObservation]:
        result = dict(accepted)
        known = sorted(accepted)
        position = {f: i for i, f in enumerate(processed_frames)}
        for start, end in zip(known, known[1:]):
            gap = position[end] - position[start]
            if gap <= 1 or gap > self.config.max_interpolation_gap:
                continue
            a, b = accepted[start], accepted[end]
            for step in range(1, gap):
                frame_idx = processed_frames[position[start] + step]
                t = step / gap
                result[frame_idx] = BallObservation(
                    frame_idx=frame_idx,
                    center=(1 - t) * a.center + t * b.center,
                    confidence=min(a.confidence, b.confidence),
                    interpolated=True,
                )
        return result
