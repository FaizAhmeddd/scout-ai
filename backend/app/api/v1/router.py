from fastapi import APIRouter

from app.api.v1.endpoints import analysis, auth, health, videos

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(analysis.router, prefix="/analyses", tags=["analyses"])
