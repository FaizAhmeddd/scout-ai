import bisect
import logging
from dataclasses import dataclass

import numpy as np

from app.core.app_config import ReIdConfig, StitchingConfig
from app.engine.domain.models import CameraMotion, PlayerObservation, PlayerTrack, TeamAssignment
from app.engine.teams.team_classifier import shirt_feature
from app.engine.tracking.thumbnails import pick_thumbnail

logger = logging.getLogger(__name__)


@dataclass
class _Fragment:
    track_id: int
    team_id: int
    observations: list[PlayerObservation]
    start_point: np.ndarray
    end_point: np.ndarray
    start_segment: int
    end_segment: int
    shirt: np.ndarray | None  # mean shirt colour histogram
    start_appearance: np.ndarray | None  # mean ReID embedding of the first frames
    end_appearance: np.ndarray | None  # mean ReID embedding of the last frames

    @property
    def first_frame(self) -> int:
        return self.observations[0].frame_idx

    @property
    def last_frame(self) -> int:
        return self.observations[-1].frame_idx


class TrackStitcher:
    """Merges tracker fragments that belong to the same player (ID switches after occlusion or leaving frame).

    Two fragments link when they are on the same team and camera shot, do not overlap in time, the later
    one starts where the earlier one could have run to during the gap, their shirt colours match and - the
    decisive cue between team-mates in identical kits - their ReID appearance embeddings match. A strong
    appearance match also re-links a player who left the shot for longer (up to `reid.long_gap_seconds`).
    Links are accepted greedily by cost so each fragment has at most one predecessor and one successor.
    """

    def __init__(self, config: StitchingConfig, fps: float, min_keypoint_conf: float, reid: ReIdConfig | None = None):
        self.config = config
        self.reid = reid or ReIdConfig(enabled=False)
        self.fps = fps
        self.min_keypoint_conf = min_keypoint_conf

    def stitch(
        self,
        tracks: dict[int, list[PlayerObservation]],
        teams: TeamAssignment,
        camera: CameraMotion,
    ) -> list[PlayerTrack]:
        fragments = {tid: self._fragment(tid, obs, teams, camera) for tid, obs in tracks.items() if obs}
        successor, predecessor = self._link(fragments)

        players = []
        for head in sorted(tid for tid in fragments if tid not in predecessor):
            chain = [head]
            while chain[-1] in successor:
                chain.append(successor[chain[-1]])
            observations = [o for tid in chain for o in fragments[tid].observations]
            team_id = fragments[head].team_id
            players.append(
                PlayerTrack(
                    player_id=head,
                    team_id=team_id,
                    source_track_ids=chain,
                    observations=observations,
                    thumbnail=pick_thumbnail(observations, teams.centers_lab.get(team_id)),
                )
            )
        logger.info("Stitched %d tracker fragments into %d player identities", len(fragments), len(players))
        return players

    def _fragment(
        self, tid: int, observations: list[PlayerObservation], teams: TeamAssignment, camera: CameraMotion
    ) -> _Fragment:
        first, last = observations[0], observations[-1]
        hists = [o.torso_hist for o in observations if o.torso_hist is not None]
        return _Fragment(
            track_id=tid,
            team_id=teams.team_of_track[tid],
            observations=observations,
            start_point=camera.stabilize(first.frame_idx, first.foot_point(self.min_keypoint_conf)),
            end_point=camera.stabilize(last.frame_idx, last.foot_point(self.min_keypoint_conf)),
            start_segment=camera.segment_id(first.frame_idx),
            end_segment=camera.segment_id(last.frame_idx),
            shirt=shirt_feature(np.mean(np.stack(hists), axis=0)) if hists else None,
            start_appearance=self._edge_appearance(observations),
            end_appearance=self._edge_appearance(observations[::-1]),
        )

    def _edge_appearance(self, observations: list[PlayerObservation]) -> np.ndarray | None:
        if not self.reid.enabled:
            return None
        embeddings = [o.reid_embedding for o in observations if o.reid_embedding is not None][: self.reid.edge_embeddings]
        if not embeddings:
            return None
        mean = np.mean(np.stack(embeddings).astype(np.float32), axis=0)
        norm = float(np.linalg.norm(mean))
        return mean / norm if norm > 1e-6 else None

    def _link(self, fragments: dict[int, _Fragment]) -> tuple[dict[int, int], dict[int, int]]:
        max_gap_frames = self.config.max_gap_seconds * self.fps
        long_gap_frames = max(max_gap_frames, self.reid.long_gap_seconds * self.fps) if self.reid.enabled else max_gap_frames
        candidates: list[tuple[float, int, int]] = []
        ordered = sorted(fragments.values(), key=lambda f: f.first_frame)
        starts = [f.first_frame for f in ordered]

        for a in ordered:
            for b in ordered[bisect.bisect_right(starts, a.last_frame):]:
                gap = b.first_frame - a.last_frame
                if gap > long_gap_frames:
                    break
                if a.team_id != b.team_id or a.end_segment != b.start_segment:
                    continue
                appearance = _cosine_distance(a.end_appearance, b.start_appearance)
                if appearance is not None and appearance > self.reid.max_link_distance:
                    continue
                if gap > max_gap_frames and (appearance is None or appearance > self.reid.long_gap_max_distance):
                    continue
                reach = self.config.base_radius_px + self.config.max_speed_px_per_frame * gap
                distance = float(np.linalg.norm(b.start_point - a.end_point))
                if distance > reach:
                    continue
                shirt_distance = (
                    float(np.linalg.norm(a.shirt - b.shirt)) if a.shirt is not None and b.shirt is not None else 0.0
                )
                if shirt_distance > self.config.max_shirt_distance:
                    continue
                cost = (
                    distance / reach
                    + shirt_distance / self.config.max_shirt_distance
                    + gap / long_gap_frames
                    + (2.0 * appearance / self.reid.max_link_distance if appearance is not None else 1.0)
                )
                candidates.append((cost, a.track_id, b.track_id))

        successor: dict[int, int] = {}
        predecessor: dict[int, int] = {}
        for _, a_id, b_id in sorted(candidates):
            if a_id in successor or b_id in predecessor:
                continue
            successor[a_id] = b_id
            predecessor[b_id] = a_id
        return successor, predecessor


def _cosine_distance(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    """1 - cosine similarity of two L2-normalised embeddings (0 = same appearance, 2 = opposite)."""
    if a is None or b is None:
        return None
    return float(1.0 - np.dot(a, b))
