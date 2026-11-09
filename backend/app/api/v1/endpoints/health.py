from fastapi import APIRouter

from app.core.config import settings
from app.db import mongo

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "database": "ok" if mongo.ping() else "unreachable",
        "gemini": "configured" if settings.GEMINI_API_KEY else "missing key",
    }
