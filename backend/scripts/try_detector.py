"""Quick check of the football detector on a short clip.

    uv run python scripts/try_detector.py [video] [frames]

Prints people per frame, unique track IDs, roles, keypoint quality and peak GPU memory.
"""

import collections
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.app_config import get_app_config  # noqa: E402
from app.engine.detection.football_tracker import FootballTracker  # noqa: E402

video = sys.argv[1] if len(sys.argv) > 1 else "data/samples/0bfacc_0.mp4"
frames = int(sys.argv[2]) if len(sys.argv) > 2 else 60

config = get_app_config()
started = time.time()
tracker = FootballTracker(
    config.detector, config.pose, config.resolve(config.detector.tracker), config.reid,
    config.resolve(config.paths.models_dir), config.resolve(config.paths.cache_dir) / "trackers",
)
print(f"model load: {time.time() - started:.1f} s")

capture = cv2.VideoCapture(video)
per_frame, track_ids, roles, keypoints = [], set(), collections.Counter(), []
started = time.time()
for index in range(frames):
    ok, frame = capture.read()
    if not ok:
        break
    observations = tracker.track(frame, index)
    per_frame.append(len(observations))
    track_ids |= {o.track_id for o in observations}
    roles.update(o.role for o in observations)
    keypoints += [float((o.keypoints[:, 2] > 0.35).sum()) for o in observations]

print(f"frames: {len(per_frame)}   {(time.time() - started) / max(len(per_frame), 1):.2f} s/frame")
print(f"people per frame: mean {np.mean(per_frame):.1f}, min {min(per_frame)}, max {max(per_frame)}")
print(f"unique track ids: {len(track_ids)}   roles: {dict(roles)}")
print(f"mean confident keypoints per person: {np.mean(keypoints):.1f} / 17")
if torch.cuda.is_available():
    print(f"peak GPU memory: {torch.cuda.max_memory_allocated() / 1e6:.0f} MB")
