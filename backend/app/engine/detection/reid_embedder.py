import logging
from pathlib import Path

import numpy as np
from ultralytics.trackers.utils.reid import ReID
from ultralytics.utils.downloads import attempt_download_asset

from app.core.app_config import ReIdConfig
from app.engine.detection.model_loader import resolve_device
from app.engine.domain.models import PlayerObservation

logger = logging.getLogger(__name__)


def reid_model_path(config: ReIdConfig, models_dir: Path) -> Path:
    """Local path of the ReID model, downloading official Ultralytics ReID assets on first use."""
    models_dir.mkdir(parents=True, exist_ok=True)
    return Path(attempt_download_asset(str(models_dir / config.model)))


class ReIdEmbedder:
    """Appearance embeddings (YOLO26 person ReID, 512-d, L2-normalised) for player crops.

    The tracker uses the same model frame-to-frame; these stored embeddings let the identity stitcher tell
    team-mates in identical kits apart and re-link a player who leaves and re-enters the shot.
    """

    def __init__(self, config: ReIdConfig, models_dir: Path, device_preference: str):
        self.config = config
        self.encoder = ReID(str(reid_model_path(config, models_dir)), device=resolve_device(device_preference))

    def embed(self, frame: np.ndarray, observations: list[PlayerObservation]) -> None:
        if not observations:
            return
        boxes = np.stack([o.bbox for o in observations])
        xywh = np.column_stack([
            (boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2,
            boxes[:, 2] - boxes[:, 0], boxes[:, 3] - boxes[:, 1],
        ]).astype(np.float32)
        for obs, feature in zip(observations, self.encoder(frame, xywh)):
            if feature is None:
                continue
            norm = float(np.linalg.norm(feature))
            if norm > 1e-6:
                obs.reid_embedding = (np.asarray(feature, dtype=np.float32) / norm).astype(np.float16)
