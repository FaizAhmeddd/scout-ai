import logging
import uuid
from functools import lru_cache
from pathlib import Path

import cv2
from fastapi import HTTPException, UploadFile, status
from pymongo.database import Database
from rich.console import Console

from app.services.job_errors import public_error
from app.core.app_config import get_app_config
from app.core.config import settings
from app.db.mongo import get_database
from app.engine.pipeline.match_analysis_pipeline import MatchAnalysisPipeline, PreparedMatch
from app.engine.render.palette import bgr_to_hex
from app.repositories.analyses import AnalysisRepository
from app.repositories.videos import VideoRepository
from app.schemas.video import JobProgress, PlayerOption, TeamOption, VideoOut
from app.services import jobs
from app.storage import local_storage

logger = logging.getLogger(__name__)

_PREPARE_STAGES = {
    "tracking": (0.0, 92.0, "Tracking players, ball and pitch"),
    "teams": (92.0, 99.0, "Identifying teams and repairing player identities"),
}
_THUMBNAIL_POSITION = 0.15
_THUMBNAIL_WIDTH = 640


async def upload(db: Database, owner_id: str, file: UploadFile, title: str) -> VideoOut:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in local_storage.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported video type '{extension or 'unknown'}'")

    video_id = uuid.uuid4().hex
    path = local_storage.upload_dir() / f"{video_id}{extension}"
    try:
        size = await local_storage.save_upload(file, path)
    except local_storage.UploadTooLarge as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc

    try:
        metadata = _probe(path)
        thumbnail = _thumbnail(path, metadata["frame_count"], local_storage.video_output_dir(video_id) / "thumbnail.jpg")
    except ValueError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    video = VideoRepository(db).insert({
        "_id": video_id,
        "owner_id": owner_id,
        "title": title.strip() or Path(file.filename).stem,
        "filename": file.filename,
        "path": str(path),
        "size_bytes": size,
        "duration_s": metadata["frame_count"] / metadata["fps"],
        "fps": metadata["fps"],
        "width": metadata["width"],
        "height": metadata["height"],
        "thumbnail_url": local_storage.public_url(thumbnail),
        "status": "queued",
        "progress": JobProgress(stage="queued", percent=0, message="Waiting for the analysis worker").model_dump(),
        "teams": [],
    })
    start_preparation(video_id)
    return to_video_out(video)


def start_preparation(video_id: str) -> None:
    jobs.submit(lambda: _prepare_job(video_id), name=f"prepare:{video_id}")


def retry_preparation(db: Database, owner_id: str, video_id: str) -> VideoOut:
    video = require_video(db, owner_id, video_id)
    if video["status"] in ("queued", "preparing"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Detection is already running for this video")
    VideoRepository(db).update(video_id, {"status": "queued", "error": None,
                                          "progress": JobProgress(stage="queued", percent=0, message="Waiting for the analysis worker").model_dump()})
    start_preparation(video_id)
    return to_video_out(require_video(db, owner_id, video_id))


def list_videos(db: Database, owner_id: str) -> list[VideoOut]:
    counts = AnalysisRepository(db).counts_by_video(owner_id)
    return [to_video_out(v, counts.get(v["_id"], {})) for v in VideoRepository(db).list(owner_id)]


def get_video(db: Database, owner_id: str, video_id: str) -> VideoOut:
    video = require_video(db, owner_id, video_id)
    counts = AnalysisRepository(db).counts_by_video(owner_id).get(video_id, {})
    return to_video_out(video, counts)


def delete_video(db: Database, owner_id: str, video_id: str) -> None:
    video = require_video(db, owner_id, video_id)
    analyses = AnalysisRepository(db)
    if video["status"] in ("queued", "preparing") or any(
        a["status"] in ("queued", "running") for a in analyses.list_for_video(owner_id, video_id)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "This video is still being processed - try again when it finishes")
    analyses.delete_for_video(owner_id, video_id)
    VideoRepository(db).delete(owner_id, video_id)
    local_storage.delete_video_files(Path(video["path"]), video_id)


def require_video(db: Database, owner_id: str, video_id: str) -> dict:
    video = VideoRepository(db).get(owner_id, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    return video


def to_video_out(video: dict, analysis_counts: dict[str, int] | None = None) -> VideoOut:
    counts = analysis_counts or {}
    return VideoOut(
        id=video["_id"],
        title=video["title"],
        filename=video["filename"],
        status=video["status"],
        progress=video.get("progress"),
        error=video.get("error"),
        duration_s=round(video["duration_s"], 1),
        fps=round(video["fps"], 2),
        width=video["width"],
        height=video["height"],
        size_mb=round(video["size_bytes"] / 1_048_576, 1),
        thumbnail_url=video.get("thumbnail_url"),
        teams=video.get("teams", []),
        analyses_total=sum(counts.values()),
        analyses_completed=counts.get("completed", 0),
        analyses_running=counts.get("queued", 0) + counts.get("running", 0),
        detection_outdated=is_detection_outdated(video),
        created_at=video["created_at"],
        updated_at=video["updated_at"],
    )


def is_detection_outdated(video: dict) -> bool:
    """True when players were detected with different tracking settings than the current ones."""
    return video["status"] == "ready" and video.get("tracking_signature") != current_tracking_signature()


@lru_cache
def current_tracking_signature() -> str:
    return build_pipeline(None).tracking_signature()


def build_pipeline(progress) -> MatchAnalysisPipeline:
    return MatchAnalysisPipeline(get_app_config(), settings.GEMINI_API_KEY, Console(quiet=True), progress=progress)


def _prepare_job(video_id: str) -> None:
    db = get_database()
    videos = VideoRepository(db)
    video = videos.get_any(video_id)
    if video is None:
        return

    def persist(progress: JobProgress) -> None:
        videos.update(video_id, {"progress": progress.model_dump()})

    videos.update(video_id, {"status": "preparing"})
    try:
        pipeline = build_pipeline(jobs.StageProgress(_PREPARE_STAGES, persist))
        prepared = pipeline.prepare(Path(video["path"]), output_dir=local_storage.video_output_dir(video_id) / "selection")
        teams = [t.model_dump() for t in _team_options(prepared)]
        signature = pipeline.tracking_signature()
    except Exception as exc:  # noqa: BLE001 - any failure must be reported on the video, not lost in the worker
        logger.exception("Detection failed for video %s", video_id)
        videos.update(video_id, {"status": "failed", "error": public_error(exc)})
        return
    videos.update(video_id, {
        "status": "ready",
        "teams": teams,
        "tracking_signature": signature,
        "error": None,
        "progress": JobProgress(stage="done", percent=100, message="Teams and players detected").model_dump(),
    })


def _team_options(prepared: PreparedMatch) -> list[TeamOption]:
    selection = prepared.selection
    options = []
    for number, team_id in enumerate(selection.team_ids(), start=1):
        players = []
        for index, player in enumerate(selection.team_players(team_id), start=1):
            thumb = prepared.output_dir / f"team{number}_player{index}.jpg"
            cv2.imwrite(str(thumb), player.thumbnail)
            players.append(PlayerOption(
                number=index,
                player_id=player.player_id,
                on_screen_s=round(selection.on_screen_s(player), 1),
                thumbnail_url=local_storage.public_url(thumb),
            ))
        options.append(TeamOption(
            number=number,
            color_name=prepared.teams.color_names[team_id],
            color_hex=bgr_to_hex(prepared.teams.colors_bgr[team_id]),
            players=players,
        ))
    return options


def _probe(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("The file could not be read as a video")
        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frame_count <= 0:
            raise ValueError("The video has no readable frames")
        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
    finally:
        capture.release()


def _thumbnail(path: Path, frame_count: int, destination: Path) -> Path:
    capture = cv2.VideoCapture(str(path))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_count * _THUMBNAIL_POSITION))
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        raise ValueError("Could not read a frame for the thumbnail")
    scale = _THUMBNAIL_WIDTH / frame.shape[1]
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), cv2.resize(frame, None, fx=scale, fy=scale), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return destination
