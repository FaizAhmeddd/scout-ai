import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from pymongo.database import Database

from app.services.job_errors import public_error
from app.db.mongo import get_database
from app.engine.interactive.target_selector import PresetTargetSelector
from app.repositories.analyses import AnalysisRepository
from app.repositories.videos import VideoRepository
from app.schemas.analysis import AnalysisCreate, AnalysisDetail, AnalysisOut, AnalysisResult, AnalysisTarget
from app.schemas.video import JobProgress
from app.services import jobs
from app.services.video_service import build_pipeline, is_detection_outdated, require_video
from app.storage import local_storage

logger = logging.getLogger(__name__)

_ANALYSIS_STAGES = {
    "tracking": (0.0, 4.0, "Loading cached tracking"),
    "teams": (4.0, 7.0, "Restoring teams and player identities"),
    "selection": (7.0, 8.0, "Locking onto the target"),
    "metrics": (8.0, 14.0, "Computing physical, pose and possession metrics"),
    "gemini": (14.0, 45.0, "AI video analysis - counting passes, dribbles, duels..."),
    "fusion": (45.0, 48.0, "Fusing tracking with AI-detected events and computing ratings"),
    "rendering": (48.0, 90.0, "Rendering the annotated pose video"),
    "reporting": (90.0, 99.0, "Building graphs, player card and report"),
}


def create(db: Database, owner_id: str, video_id: str, request: AnalysisCreate) -> AnalysisOut:
    video = require_video(db, owner_id, video_id)
    if video["status"] != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Teams and players are not detected yet for this video")
    if is_detection_outdated(video):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Player tracking was upgraded since this video was processed - re-run detection so player numbers match",
        )
    teams = video.get("teams", [])
    if request.team > len(teams):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Team must be between 1 and {len(teams)}")
    team = teams[request.team - 1]
    player = None
    if request.player is not None:
        if request.player > len(team["players"]):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Player must be between 1 and {len(team['players'])}")
        player = team["players"][request.player - 1]

    target = AnalysisTarget(
        mode="player" if player else "team",
        team=request.team,
        team_color=team["color_name"],
        team_color_hex=team["color_hex"],
        player=request.player,
        jersey_number=request.jersey_number,
        label=_label(request, team),
        thumbnail_url=player["thumbnail_url"] if player else None,
    )
    analysis = AnalysisRepository(db).insert({
        "_id": uuid.uuid4().hex,
        "owner_id": owner_id,
        "video_id": video_id,
        "video_title": video["title"],
        "video_thumbnail_url": video.get("thumbnail_url"),
        "target": target.model_dump(),
        "request": request.model_dump(),
        "use_gemini": request.use_gemini,
        "render_video": request.render_video,
        "status": "queued",
        "progress": JobProgress(stage="queued", percent=0, message="Waiting for the analysis worker").model_dump(),
    })
    jobs.submit(lambda: _run_job(analysis["_id"]), name=f"analysis:{analysis['_id']}")
    return to_analysis_out(analysis)


def list_for_video(db: Database, owner_id: str, video_id: str) -> list[AnalysisOut]:
    require_video(db, owner_id, video_id)
    return [to_analysis_out(a) for a in AnalysisRepository(db).list_for_video(owner_id, video_id)]


def list_recent(db: Database, owner_id: str) -> list[AnalysisOut]:
    return [to_analysis_out(a) for a in AnalysisRepository(db).list_recent(owner_id)]


def get(db: Database, owner_id: str, analysis_id: str) -> AnalysisDetail:
    analysis = _require(db, owner_id, analysis_id)
    return AnalysisDetail(**to_analysis_out(analysis).model_dump(), metrics=(analysis.get("result") or {}).get("metrics"))


def delete(db: Database, owner_id: str, analysis_id: str) -> None:
    analysis = _require(db, owner_id, analysis_id)
    if analysis["status"] in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This analysis is still running")
    AnalysisRepository(db).delete(owner_id, analysis_id)
    shutil.rmtree(local_storage.video_output_dir(analysis["video_id"]) / f"analysis_{analysis_id}", ignore_errors=True)


def to_analysis_out(analysis: dict) -> AnalysisOut:
    result = analysis.get("result")
    return AnalysisOut(
        id=analysis["_id"],
        video_id=analysis["video_id"],
        video_title=analysis["video_title"],
        video_thumbnail_url=analysis.get("video_thumbnail_url"),
        target=analysis["target"],
        use_gemini=analysis["use_gemini"],
        render_video=analysis["render_video"],
        status=analysis["status"],
        progress=analysis.get("progress"),
        error=analysis.get("error"),
        result=AnalysisResult(**{k: v for k, v in result.items() if k != "metrics"}) if result else None,
        headline=analysis.get("headline"),
        created_at=analysis["created_at"],
        completed_at=analysis.get("completed_at"),
    )


def _require(db: Database, owner_id: str, analysis_id: str) -> dict:
    analysis = AnalysisRepository(db).get(owner_id, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return analysis


def _label(request: AnalysisCreate, team: dict) -> str:
    if request.player is None:
        return f"Team {request.team} ({team['color_name']})"
    if request.player_name.strip():
        return request.player_name.strip()
    return f"#{request.jersey_number}" if request.jersey_number is not None else f"Player {request.player}"


def _run_job(analysis_id: str) -> None:
    db = get_database()
    analyses = AnalysisRepository(db)
    analysis = analyses.get_any(analysis_id)
    video = VideoRepository(db).get_any(analysis["video_id"]) if analysis else None
    if analysis is None or video is None:
        return

    def persist(progress: JobProgress) -> None:
        analyses.update(analysis_id, {"progress": progress.model_dump()})

    request = AnalysisCreate(**analysis["request"])
    analyses.update(analysis_id, {"status": "running", "started_at": datetime.now(UTC)})
    try:
        pipeline = build_pipeline(jobs.StageProgress(_ANALYSIS_STAGES, persist))
        prepared = pipeline.prepare(
            Path(video["path"]), output_dir=local_storage.video_output_dir(video["_id"]) / f"analysis_{analysis_id}"
        )
        selector = PresetTargetSelector(request.team, request.player, request.jersey_number, analysis["target"]["label"])
        outputs = pipeline.analyze(prepared, selector, use_gemini=request.use_gemini, render_video=request.render_video)
    except Exception as exc:  # noqa: BLE001 - any failure must be reported on the analysis, not lost in the worker
        logger.exception("Analysis %s failed", analysis_id)
        analyses.update(analysis_id, {"status": "failed", "error": public_error(exc)})
        return

    metrics = json.loads(outputs.metrics_json.read_text(encoding="utf-8"))
    url = local_storage.public_url
    analyses.update(analysis_id, {
        "status": "completed",
        "completed_at": datetime.now(UTC),
        "progress": JobProgress(stage="done", percent=100, message="Analysis complete").model_dump(),
        "headline": _headline(metrics),
        "result": {
            "report_url": url(outputs.report_html),
            "annotated_video_url": url(outputs.annotated_video) if outputs.annotated_video else None,
            "player_card_url": url(outputs.player_card) if outputs.player_card else None,
            "metrics_url": url(outputs.metrics_json),
            "gemini_events_url": url(outputs.gemini_json) if outputs.gemini_json else None,
            "chart_urls": {name: url(path) for name, path in outputs.charts.items()},
            "metrics": metrics,
        },
    })


def _headline(metrics: dict[str, Any]) -> dict[str, Any]:
    """Compact KPIs shown on library cards without loading the full metrics document."""
    player = metrics.get("focus_player")
    team = metrics["team"]
    headline: dict[str, Any] = {"gemini_status": metrics.get("gemini_status"), "geometry": metrics.get("geometry_mode")}
    if player:
        events = player.get("events") or {}
        headline |= {
            "overall": player["ratings"]["overall"],
            "position": player["ratings"]["position"],
            "distance_m": player["physical"]["total_distance_m"],
            "top_speed_kmh": player["physical"]["top_speed_kmh"],
            "passes": f"{events.get('passes_completed', 0)}/{events.get('passes_attempted', 0)}" if events else None,
        }
    else:
        headline |= {
            "possession": team.get("possession_share"),
            "players": len(team.get("players", [])),
            "distance_m": round(sum(p["physical"]["total_distance_m"] or 0 for p in team.get("players", [])), 1),
        }
    return headline
