import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError

from app.api.v1.router import api_router
from app.core.config import settings
from app.db import mongo
from app.repositories.analyses import AnalysisRepository
from app.repositories.videos import VideoRepository
from app.services import auth_service
from app.storage.local_storage import OUTPUTS_URL_PREFIX, outputs_root

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        db = mongo.get_database()
        mongo.ensure_indexes(db)
        interrupted = VideoRepository(db).fail_interrupted() + AnalysisRepository(db).fail_interrupted()
        if interrupted:
            logger.warning("Marked %d jobs interrupted by the previous shutdown as failed", interrupted)
        if auth_service.ensure_demo_user(db):
            logger.info("Created demo account %s", settings.DEMO_USER_EMAIL)
    except PyMongoError as exc:
        logger.error("MongoDB is unreachable at startup (%s) - is the VPN connected?", exc)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

outputs_root().mkdir(parents=True, exist_ok=True)
app.mount(OUTPUTS_URL_PREFIX, StaticFiles(directory=outputs_root()), name="outputs")
