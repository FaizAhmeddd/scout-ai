import logging
from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import settings

logger = logging.getLogger(__name__)

USERS = "users"
VIDEOS = "videos"
ANALYSES = "analyses"


@lru_cache
def get_client() -> MongoClient:
    return MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000, tz_aware=True)


def get_database() -> Database:
    return get_client()[settings.MONGODB_DB_NAME]


def ping() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except PyMongoError:
        return False


def ensure_indexes(db: Database) -> None:
    db[USERS].create_index([("email", ASCENDING)], unique=True)
    db[VIDEOS].create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    db[ANALYSES].create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    db[ANALYSES].create_index([("video_id", ASCENDING), ("created_at", DESCENDING)])
