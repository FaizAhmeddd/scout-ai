import logging

import cv2
import numpy as np

from app.core.app_config import PresenceConfig
from app.engine.domain.models import PlayerObservation

logger = logging.getLogger(__name__)


def grass_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))


class PitchPresenceFilter:
    """Separates players from everyone else in shot (coaches, substitutes, stewards, ball kids, crowd).

    A person counts as a player when their feet stand on pitch grass for most of their track and, when
    the pitch is calibrated, their ground position projects inside the touchlines.
    """

    def __init__(self, config: PresenceConfig, pitch_length_m: float, pitch_width_m: float):
        self.config = config
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m

    def feet_on_grass(self, frame: np.ndarray, obs: PlayerObservation) -> bool:
        x0, _, x1, y1 = obs.bbox
        h = obs.box_height
        top = int(max(y1 - 0.08 * h, 0))
        bottom = int(min(y1 + 0.12 * h, frame.shape[0]))
        left, right = int(max(x0, 0)), int(min(x1, frame.shape[1]))
        if bottom - top < 2 or right - left < 2:
            return False
        patch = frame[top:bottom, left:right]
        return float((grass_mask(patch) > 0).mean()) >= self.config.min_grass_fraction

    def keep_players(
        self, tracks: dict[int, list[PlayerObservation]], homographies: dict[int, np.ndarray]
    ) -> dict[int, list[PlayerObservation]]:
        kept = {}
        for tid, observations in tracks.items():
            if np.mean([o.on_grass for o in observations]) < self.config.min_track_on_grass:
                continue
            on_pitch = self._on_pitch_share(observations, homographies)
            if on_pitch is not None and on_pitch < self.config.min_track_on_pitch:
                continue
            kept[tid] = observations
        logger.info("On-pitch filter kept %d of %d tracks (removed coaches, stewards, crowd)", len(kept), len(tracks))
        return kept

    def _on_pitch_share(self, observations: list[PlayerObservation], homographies: dict[int, np.ndarray]) -> float | None:
        margin = self.config.pitch_margin_m
        inside = []
        for obs in observations:
            homography = homographies.get(obs.frame_idx)
            if homography is None:
                continue
            x, y = cv2.perspectiveTransform(obs.foot_point().astype(np.float64).reshape(1, 1, 2), homography).reshape(2)
            inside.append(-margin <= x <= self.pitch_length + margin and -margin <= y <= self.pitch_width + margin)
        return float(np.mean(inside)) if inside else None
