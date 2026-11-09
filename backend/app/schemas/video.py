from datetime import datetime

from pydantic import BaseModel


class JobProgress(BaseModel):
    stage: str
    percent: float
    message: str = ""


class PlayerOption(BaseModel):
    number: int
    player_id: int
    on_screen_s: float
    thumbnail_url: str


class TeamOption(BaseModel):
    number: int
    color_name: str
    color_hex: str
    players: list[PlayerOption]


class VideoOut(BaseModel):
    id: str
    title: str
    filename: str
    status: str  # queued | preparing | ready | failed
    progress: JobProgress | None = None
    error: str | None = None
    duration_s: float
    fps: float
    width: int
    height: int
    size_mb: float
    thumbnail_url: str | None = None
    teams: list[TeamOption] = []
    analyses_total: int = 0
    analyses_completed: int = 0
    analyses_running: int = 0
    detection_outdated: bool = False  # tracking was upgraded since players were detected
    created_at: datetime
    updated_at: datetime
