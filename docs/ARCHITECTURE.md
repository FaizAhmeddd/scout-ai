# Architecture

## Flow

```
upload ──▶ probe + thumbnail ──▶ [detect job] ──▶ teams + players ready
                                      │
              user picks team / player ▼
                              [analysis job] ──▶ metrics ▶ AI events ▶ fusion ▶ render ▶ report
```

Both jobs run in the in-process single-worker pool (`backend/app/services/jobs.py`), write progress to MongoDB, and
are polled by the frontend. The CLI (`backend/main.py`) calls the same `MatchAnalysisPipeline`.

## Engine pipeline (`backend/app/engine/pipeline/match_analysis_pipeline.py`)

Pass 1 — `prepare()` (cached per video + settings in `.cache/stages`):

1. **Tracking** (`_run_tracking`), per frame:
   - `detection/football_tracker.py` — RF-DETR (SoccerNet) detects players / goalkeepers / referees / ball →
     TrackTrack tracker with YOLO26 ReID embeddings → `crop_pose.py` runs YOLO26n-pose on each player crop.
     `detector.type: pose` swaps this for `pose_tracker.py` (whole-frame pose + Ultralytics built-in tracking).
   - `teams/shirt_color.py` shirt histogram from the torso polygon, `tracking/pitch_presence.py` feet-on-grass test,
     `tracking/thumbnails.py`, `detection/reid_embedder.py` (sampled embeddings for stitching).
   - `detection/ball_detector.py` (+ detector ball candidates) → `BallTrajectoryBuilder` filters and interpolates.
   - `motion/camera_motion_estimator.py` Lucas-Kanade camera motion and scene cuts (tracks are split at cuts).
   - `detection/pitch_detector.py` 32 pitch keypoints → per-frame homography (real metres).
2. **Teams and identities**: presence filter (drops coaches/stewards), `teams/team_classifier.py`
   (kit clustering, tracker-ID-swap splitting, referees → other, goalkeepers → nearest team by position),
   `tracking/track_stitcher.py` (re-links fragments by position, shirt colour and ReID appearance).

Pass 2 — `analyze()`:

3. `geometry/view_transformer.py` pixels → metres (manual homography > pitch keypoints > pose-height scale).
4. `metrics/kinematics.py`, `possession.py`, `pose_metrics.py` — see [METRICS.md](METRICS.md).
5. `gemini/agentic_analyst.py` — agentic video understanding returns a timestamped, schema-validated event log.
6. `fusion/` — `event_counts.py`, `rating_model.py` (FC-style PAC/SHO/PAS/DRI/DEF/PHY + overall),
   `report_builder.py` (caveats, per-player and team reports).
7. `render/` annotated video + minimap, `reports/` charts, player card, `report.html`, `serializer.py` → `metrics.json`.

## Backend app layer (`backend/app`)

| Path | Role |
|---|---|
| `main.py` | FastAPI app: lifespan (indexes, fail interrupted jobs, ensure demo user), `/outputs` static mount |
| `api/endpoints/` | `auth`, `videos`, `analysis`, `health` routers; `api/deps.py` auth dependency |
| `services/` | `video_service` (upload, detect job), `analysis_service`, `auth_service`, `jobs`, `job_errors` (friendly failures) |
| `repositories/`, `db/mongo.py` | sync PyMongo repositories (users, videos, analyses) |
| `core/` | `config.py` env settings, `app_config.py` typed `config.yaml` |
| `storage/local_storage.py` | uploads (size-limited), per-video output dirs, public URLs |

A video stores a **tracking signature**; if the signature of the current engine differs, detection is *outdated*
and analyses return 409 until the user re-runs detection.

## Frontend (`frontend/src`)

React 18 + Vite, `react-router`, `motion`, `lucide-react`, custom CSS. Pages: Landing, Login/Signup, Library, Upload,
VideoDetail (pick team/player), Analyses, AnalysisDetail (results tabs incl. "How it's measured"). Shared:
`services/apiClient.js` (timeouts, error mapping, 401 handling), `hooks/usePolling.js` (job polling with backoff),
`components/ui/States.jsx` + `ErrorBoundary.jsx` (loading/error/empty/not-found), `utils/format.js` (safe formatters,
`cleanText` strips vendor/hardware words from server text).

## Where to change what

| Goal | Touch |
|---|---|
| New tunable | `config/config.yaml` + `app/core/app_config.py`; add to `_tracking_parts()` if it affects tracking |
| New metric | `engine/metrics/*`, `fusion/report_builder.py`, `reports/serializer.py`, frontend `ResultBlocks.jsx`, `Methodology.jsx`, `docs/METRICS.md` |
| New event type | `engine/gemini/schemas.py` + `prompts.py`, `fusion/event_counts.py`, rating model |
| Tracker behaviour | `config/tracktrack_rfdetr.yaml` (or `tracktrack_football.yaml` for pose mode) and bump the cache version |
