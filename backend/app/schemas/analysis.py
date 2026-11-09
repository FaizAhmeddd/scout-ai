from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.video import JobProgress


class AnalysisCreate(BaseModel):
    team: int = Field(ge=1, le=2, description="Team number as listed on the video")
    player: int | None = Field(default=None, ge=1, description="Player number from the team list; null = whole team")
    jersey_number: int | None = Field(default=None, ge=0, le=99)
    player_name: str = Field(default="", max_length=60)
    use_gemini: bool = True
    render_video: bool = True


class AnalysisTarget(BaseModel):
    mode: str  # player | team
    team: int
    team_color: str
    team_color_hex: str
    player: int | None = None
    jersey_number: int | None = None
    label: str
    thumbnail_url: str | None = None


class AnalysisResult(BaseModel):
    report_url: str
    annotated_video_url: str | None = None
    player_card_url: str | None = None
    metrics_url: str
    gemini_events_url: str | None = None
    chart_urls: dict[str, str] = {}


class AnalysisOut(BaseModel):
    id: str
    video_id: str
    video_title: str
    video_thumbnail_url: str | None = None
    target: AnalysisTarget
    use_gemini: bool
    render_video: bool
    status: str  # queued | running | completed | failed
    progress: JobProgress | None = None
    error: str | None = None
    result: AnalysisResult | None = None
    headline: dict[str, Any] | None = None  # compact KPIs for list cards
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisDetail(AnalysisOut):
    metrics: dict[str, Any] | None = None
