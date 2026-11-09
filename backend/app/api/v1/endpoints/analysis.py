from fastapi import APIRouter, Response, status

from app.api.deps import DbDep, UserDep
from app.schemas.analysis import AnalysisDetail, AnalysisOut
from app.services import analysis_service

router = APIRouter()


@router.get("", response_model=list[AnalysisOut])
def list_recent(db: DbDep, user: UserDep) -> list[AnalysisOut]:
    return analysis_service.list_recent(db, user["_id"])


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: str, db: DbDep, user: UserDep) -> AnalysisDetail:
    return analysis_service.get(db, user["_id"], analysis_id)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: str, db: DbDep, user: UserDep) -> Response:
    analysis_service.delete(db, user["_id"], analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
