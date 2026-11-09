import heapq

import cv2
import numpy as np

from app.engine.domain.models import PlayerObservation

_THUMBNAIL_HEIGHT = 220
_CANDIDATES_PER_TRACK = 5
_MIN_CONFIDENCE = 0.5
_ISOLATION_IOU = 0.02


class ThumbnailCollector:
    """Keeps crops for each track's few largest frames, so a clean portrait can be chosen once teams are known."""

    def __init__(self):
        self._heaps: dict[int, list[tuple[float, int, PlayerObservation]]] = {}
        self._counter = 0

    def add_frame(self, frame: np.ndarray, observations: list[PlayerObservation]) -> None:
        boxes = np.stack([o.bbox for o in observations]) if observations else np.zeros((0, 4))
        for i, obs in enumerate(observations):
            obs.isolated = _max_iou(obs.bbox, np.delete(boxes, i, axis=0)) < _ISOLATION_IOU
            if obs.confidence >= _MIN_CONFIDENCE:
                self._offer(frame, obs)

    def _offer(self, frame: np.ndarray, obs: PlayerObservation) -> None:
        heap = self._heaps.setdefault(obs.track_id, [])
        score = obs.box_height * (1.5 if obs.isolated else 1.0)
        self._counter += 1
        if len(heap) < _CANDIDATES_PER_TRACK:
            obs.thumbnail = _crop(frame, obs)
            heapq.heappush(heap, (score, self._counter, obs))
        elif score > heap[0][0]:
            obs.thumbnail = _crop(frame, obs)
            _, _, evicted = heapq.heapreplace(heap, (score, self._counter, obs))
            evicted.thumbnail = None


def pick_thumbnail(observations: list[PlayerObservation], team_center_lab: np.ndarray | None) -> np.ndarray | None:
    """Best portrait: unobstructed, wearing the team's colour, and as large as possible."""
    candidates = [o for o in observations if o.thumbnail is not None]
    if not candidates:
        return None

    def score(obs: PlayerObservation) -> float:
        colour_penalty = 0.0
        if team_center_lab is not None and obs.torso_color_lab is not None:
            colour_penalty = float(np.linalg.norm(obs.torso_color_lab - team_center_lab))
        return (100.0 if obs.isolated else 0.0) - 3.0 * colour_penalty + obs.box_height

    return max(candidates, key=score).thumbnail


def _crop(frame: np.ndarray, obs: PlayerObservation) -> np.ndarray | None:
    x0, y0, x1, y1 = obs.bbox
    pad = 0.08 * obs.box_height
    h, w = frame.shape[:2]
    crop = frame[max(int(y0 - pad), 0): min(int(y1 + pad), h), max(int(x0 - pad), 0): min(int(x1 + pad), w)]
    if crop.size == 0:
        return None
    scale = _THUMBNAIL_HEIGHT / crop.shape[0]
    return cv2.resize(crop, (max(int(crop.shape[1] * scale), 1), _THUMBNAIL_HEIGHT))


def _max_iou(box: np.ndarray, others: np.ndarray) -> float:
    if not len(others):
        return 0.0
    x0 = np.maximum(box[0], others[:, 0])
    y0 = np.maximum(box[1], others[:, 1])
    x1 = np.minimum(box[2], others[:, 2])
    y1 = np.minimum(box[3], others[:, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (others[:, 2] - others[:, 0]) * (others[:, 3] - others[:, 1])
    return float((inter / (area + areas - inter + 1e-6)).max())
