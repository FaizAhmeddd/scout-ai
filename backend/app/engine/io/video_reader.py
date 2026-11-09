from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from app.engine.domain.models import VideoInfo


class VideoReader:
    """Sequential frame reader honouring a frame stride and an optional duration cap."""

    def __init__(self, path: Path | str, frame_stride: int = 1, max_seconds: float | None = None):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Video not found: {self.path}")

        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            raise ValueError(f"OpenCV could not open video: {self.path}")
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        capture.release()

        if max_seconds is not None:
            frame_count = min(frame_count, int(max_seconds * fps))

        self.info = VideoInfo(
            path=self.path,
            fps=fps,
            width=width,
            height=height,
            frame_count=frame_count,
            frame_stride=frame_stride,
        )

    def __len__(self) -> int:
        return (self.info.frame_count + self.info.frame_stride - 1) // self.info.frame_stride

    def frames(self) -> Iterator[tuple[int, np.ndarray]]:
        capture = cv2.VideoCapture(str(self.path))
        try:
            for frame_idx in range(self.info.frame_count):
                if frame_idx % self.info.frame_stride:
                    if not capture.grab():
                        break
                    continue
                ok, frame = capture.read()
                if not ok:
                    break
                yield frame_idx, frame
        finally:
            capture.release()
