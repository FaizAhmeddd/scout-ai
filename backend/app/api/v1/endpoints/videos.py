from fastapi import APIRouter, Form, Response, UploadFile, status

from app.api.deps import DbDep, UserDep
from app.schemas.analysis import AnalysisCreate, AnalysisOut
from app.schemas.video import VideoOut
from app.services import analysis_service, video_service

router = APIRouter()


@router.post("", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
async def upload_video(db: DbDep, user: UserDep, file: UploadFile, title: str = Form("")) -> VideoOut:
    """Stores the video and immediately starts team & player detection in the background."""
    return await video_service.upload(db, user["_id"], file, title)


@router.get("", response_model=list[VideoOut])
def list_videos(db: DbDep, user: UserDep) -> list[VideoOut]:
    return video_service.list_videos(db, user["_id"])


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: str, db: DbDep, user: UserDep) -> VideoOut:
    return video_service.get_video(db, user["_id"], video_id)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: str, db: DbDep, user: UserDep) -> Response:
    video_service.delete_video(db, user["_id"], video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{video_id}/prepare", response_model=VideoOut)
def retry_detection(video_id: str, db: DbDep, user: UserDep) -> VideoOut:
    return video_service.retry_preparation(db, user["_id"], video_id)


@router.get("/{video_id}/analyses", response_model=list[AnalysisOut])
def list_video_analyses(video_id: str, db: DbDep, user: UserDep) -> list[AnalysisOut]:
    return analysis_service.list_for_video(db, user["_id"], video_id)


@router.post("/{video_id}/analyses", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(video_id: str, request: AnalysisCreate, db: DbDep, user: UserDep) -> AnalysisOut:
    """Queues a team or single-player analysis; poll GET /analyses/{id} for progress."""
    return analysis_service.create(db, user["_id"], video_id, request)
