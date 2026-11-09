from fastapi import APIRouter, status

from app.api.deps import DbDep, UserDep
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest, db: DbDep) -> TokenResponse:
    return auth_service.signup(db, request)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: DbDep) -> TokenResponse:
    return auth_service.login(db, request)


@router.get("/me", response_model=UserOut)
def me(user: UserDep) -> UserOut:
    return auth_service.to_user_out(user)
