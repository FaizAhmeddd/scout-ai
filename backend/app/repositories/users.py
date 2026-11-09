import uuid
from datetime import UTC, datetime

from pymongo.database import Database

from app.db.mongo import USERS


class UserRepository:
    def __init__(self, db: Database):
        self.collection = db[USERS]

    def create(self, email: str, full_name: str, password_hash: str) -> dict:
        user = {
            "_id": uuid.uuid4().hex,
            "email": email.lower(),
            "full_name": full_name,
            "password_hash": password_hash,
            "created_at": datetime.now(UTC),
        }
        self.collection.insert_one(user)
        return user

    def get_by_email(self, email: str) -> dict | None:
        return self.collection.find_one({"email": email.lower()})

    def get(self, user_id: str) -> dict | None:
        return self.collection.find_one({"_id": user_id})
