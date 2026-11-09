from fastapi import HTTPException, status
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut


def to_user_out(user: dict) -> UserOut:
    return UserOut(id=user["_id"], full_name=user["full_name"], email=user["email"], created_at=user["created_at"])


def signup(db: Database, request: SignupRequest) -> TokenResponse:
    users = UserRepository(db)
    try:
        user = users.create(request.email, request.full_name.strip(), hash_password(request.password))
    except DuplicateKeyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
    return TokenResponse(access_token=create_access_token(user["_id"]), user=to_user_out(user))


def ensure_demo_user(db: Database) -> bool:
    """Creates the demo account from settings if configured and missing. Returns True if it was created."""
    if not (settings.DEMO_USER_EMAIL and settings.DEMO_USER_PASSWORD):
        return False
    users = UserRepository(db)
    if users.get_by_email(settings.DEMO_USER_EMAIL):
        return False
    users.create(settings.DEMO_USER_EMAIL, settings.DEMO_USER_NAME, hash_password(settings.DEMO_USER_PASSWORD))
    return True


def login(db: Database, request: LoginRequest) -> TokenResponse:
    user = UserRepository(db).get_by_email(request.email)
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user["_id"]), user=to_user_out(user))
