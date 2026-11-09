from datetime import UTC, datetime

from pymongo import DESCENDING
from pymongo.database import Database

from app.db.mongo import VIDEOS


class VideoRepository:
    def __init__(self, db: Database):
        self.collection = db[VIDEOS]

    def insert(self, video: dict) -> dict:
        now = datetime.now(UTC)
        video.setdefault("created_at", now)
        video["updated_at"] = now
        self.collection.insert_one(video)
        return video

    def get(self, owner_id: str, video_id: str) -> dict | None:
        return self.collection.find_one({"_id": video_id, "owner_id": owner_id})

    def get_any(self, video_id: str) -> dict | None:
        return self.collection.find_one({"_id": video_id})

    def list(self, owner_id: str) -> list[dict]:
        return list(self.collection.find({"owner_id": owner_id}).sort("created_at", DESCENDING))

    def update(self, video_id: str, fields: dict) -> None:
        self.collection.update_one({"_id": video_id}, {"$set": {**fields, "updated_at": datetime.now(UTC)}})

    def delete(self, owner_id: str, video_id: str) -> bool:
        return self.collection.delete_one({"_id": video_id, "owner_id": owner_id}).deleted_count == 1

    def fail_interrupted(self) -> int:
        """Jobs cannot survive a server restart (in-process worker), so mark them failed on startup."""
        return self.collection.update_many(
            {"status": {"$in": ["queued", "preparing"]}},
            {"$set": {"status": "failed", "error": "Interrupted by a server restart - retry detection."}},
        ).modified_count
