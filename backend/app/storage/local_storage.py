import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.app_config import BACKEND_ROOT, get_app_config
from app.core.config import settings

OUTPUTS_URL_PREFIX = "/outputs"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
_CHUNK = 1024 * 1024


def upload_dir() -> Path:
    path = Path(settings.UPLOAD_DIR)
    return path if path.is_absolute() else BACKEND_ROOT / path


def outputs_root() -> Path:
    config = get_app_config()
    return config.resolve(config.paths.output_root)


def video_output_dir(video_id: str) -> Path:
    return outputs_root() / video_id


def public_url(path: Path) -> str:
    """URL under the /outputs static mount for a file inside the outputs directory."""
    return f"{OUTPUTS_URL_PREFIX}/{path.relative_to(outputs_root()).as_posix()}"


class UploadTooLarge(Exception):
    pass


async def save_upload(file: UploadFile, destination: Path) -> int:
    """Streams the upload to disk, aborting (and removing the partial file) beyond MAX_UPLOAD_MB."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with destination.open("wb") as out:
        while chunk := await file.read(_CHUNK):
            size += len(chunk)
            if size > limit:
                break
            out.write(chunk)
    if size > limit:
        destination.unlink(missing_ok=True)
        raise UploadTooLarge(f"Video is larger than the {settings.MAX_UPLOAD_MB // 1024} GB upload limit")
    return size


def delete_video_files(video_path: Path, video_id: str) -> None:
    video_path.unlink(missing_ok=True)
    shutil.rmtree(video_output_dir(video_id), ignore_errors=True)
