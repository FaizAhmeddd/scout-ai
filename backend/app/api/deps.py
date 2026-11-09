from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.core.security import decode_access_token
from app.db.mongo import get_database
from app.repositories.users import UserRepository

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Database:
    return get_database()


def get_current_user(
    db: Annotated[Database, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    user_id = decode_access_token(credentials.credentials) if credentials else None
    user = UserRepository(db).get(user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


DbDep = Annotated[Database, Depends(get_db)]
UserDep = Annotated[dict, Depends(get_current_user)]
