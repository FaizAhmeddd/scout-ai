from datetime import UTC, datetime

from pymongo import DESCENDING
from pymongo.database import Database

from app.db.mongo import ANALYSES


class AnalysisRepository:
    def __init__(self, db: Database):
        self.collection = db[ANALYSES]

    def insert(self, analysis: dict) -> dict:
        now = datetime.now(UTC)
        analysis.setdefault("created_at", now)
        analysis["updated_at"] = now
        self.collection.insert_one(analysis)
        return analysis

    def get(self, owner_id: str, analysis_id: str) -> dict | None:
        return self.collection.find_one({"_id": analysis_id, "owner_id": owner_id})

    def get_any(self, analysis_id: str) -> dict | None:
        return self.collection.find_one({"_id": analysis_id})

    def list_for_video(self, owner_id: str, video_id: str) -> list[dict]:
        return list(
            self.collection.find({"owner_id": owner_id, "video_id": video_id}, {"result.metrics": 0})
            .sort("created_at", DESCENDING)
        )

    def list_recent(self, owner_id: str, limit: int = 50) -> list[dict]:
        return list(
            self.collection.find({"owner_id": owner_id}, {"result.metrics": 0}).sort("created_at", DESCENDING).limit(limit)
        )

    def counts_by_video(self, owner_id: str) -> dict[str, dict[str, int]]:
        pipeline = [
            {"$match": {"owner_id": owner_id}},
            {"$group": {"_id": {"video": "$video_id", "status": "$status"}, "n": {"$sum": 1}}},
        ]
        counts: dict[str, dict[str, int]] = {}
        for row in self.collection.aggregate(pipeline):
            counts.setdefault(row["_id"]["video"], {})[row["_id"]["status"]] = row["n"]
        return counts

    def update(self, analysis_id: str, fields: dict) -> None:
        self.collection.update_one({"_id": analysis_id}, {"$set": {**fields, "updated_at": datetime.now(UTC)}})

    def delete(self, owner_id: str, analysis_id: str) -> bool:
        return self.collection.delete_one({"_id": analysis_id, "owner_id": owner_id}).deleted_count == 1

    def delete_for_video(self, owner_id: str, video_id: str) -> None:
        self.collection.delete_many({"owner_id": owner_id, "video_id": video_id})

    def fail_interrupted(self) -> int:
        return self.collection.update_many(
            {"status": {"$in": ["queued", "running"]}},
            {"$set": {"status": "failed", "error": "Interrupted by a server restart - run the analysis again."}},
        ).modified_count
