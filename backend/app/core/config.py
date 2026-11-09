from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.app_config import BACKEND_ROOT


class Settings(BaseSettings):
    """Environment-level settings: secrets and deployment wiring. Tunables live in config/config.yaml."""

    APP_NAME: str = "football-analysis-api"
    APP_ENV: str = "development"
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_MB: int = 4096

    GEMINI_API_KEY: str = ""

    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "hf_soccer_analysis"

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 720

    DEMO_USER_NAME: str = "Demo Analyst"
    DEMO_USER_EMAIL: str = ""
    DEMO_USER_PASSWORD: str = ""

    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")


settings = Settings()
