import logging
from pathlib import Path

import torch
from ultralytics import YOLO

logger = logging.getLogger(__name__)


def resolve_device(preference: str) -> str:
    if preference == "auto":
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    if preference.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("CUDA requested but not available — falling back to CPU")
        return "cpu"
    return preference


def load_yolo(weights: str, models_dir: Path) -> YOLO:
    """Loads weights from models_dir, letting Ultralytics download official assets there on first use."""
    candidate = Path(weights)
    if not candidate.is_absolute() and candidate.parent == Path("."):
        models_dir.mkdir(parents=True, exist_ok=True)
        candidate = models_dir / candidate.name
    logger.info("Loading YOLO weights %s", candidate)
    return YOLO(str(candidate))
