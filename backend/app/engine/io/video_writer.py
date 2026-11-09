import logging
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

logger = logging.getLogger(__name__)


class VideoWriter:
    """Writes BGR frames to mp4; optionally transcodes to browser-playable H.264 on close."""

    def __init__(self, path: Path, fps: float, size: tuple[int, int], transcode_h264: bool = True):
        self.final_path = Path(path)
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        self.transcode_h264 = transcode_h264
        self._raw_path = self.final_path.with_name(f"{self.final_path.stem}_raw.mp4") if transcode_h264 else self.final_path
        self._writer = cv2.VideoWriter(str(self._raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        if not self._writer.isOpened():
            raise RuntimeError(f"Could not open video writer for {self._raw_path}")

    def write(self, frame: np.ndarray) -> None:
        self._writer.write(frame)

    def close(self) -> Path:
        self._writer.release()
        if self.transcode_h264:
            self._transcode()
        return self.final_path

    def _transcode(self) -> None:
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-loglevel", "error",
            "-i", str(self._raw_path),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(self.final_path),
        ]
        try:
            subprocess.run(command, check=True)
            self._raw_path.unlink(missing_ok=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            logger.warning("H.264 transcode failed (%s); keeping mp4v output", exc)
            self._raw_path.replace(self.final_path)

    def __enter__(self) -> "VideoWriter":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
