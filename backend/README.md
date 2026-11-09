# Backend — ScoutAI

A pose-based football analysis engine. Give it a match video and it:

1. **Detects every player, goalkeeper and referee** with **RF-DETR fine-tuned on SoccerNet**, tracks them with **TrackTrack + YOLO26 ReID** (appearance embeddings keep IDs through crossings and occlusions), runs **YOLO26n-pose on each player crop** (17 body keypoints even for distant players), detects the **ball** with a football-trained detector, and **calibrates the pitch automatically** from 32 detected pitch landmarks.
2. **Splits players into teams** by shirt colour sampled from the pose torso (referees excluded, goalkeepers joined to their team by position), repairs tracker ID switches, and asks **which team** and **which player (or the whole team)** to analyse.
3. Computes **physical metrics** (distance, FIFA EPTS speed zones, top speed, sprints, accelerations), **pose biomechanics** (running cadence, trunk lean) and **ball possession**.
4. Sends the video to **Gemini 3.7 Flash in agentic video mode**, which logs every **pass, dribble, shot, tackle, interception, duel, cross, foul…** with timestamps.
5. Fuses both into **FC/FIFA-style ratings** (PAC/SHO/PAS/DRI/DEF/PHY + OVR) and produces:
   - `annotated.mp4` with pose skeletons, team colours, a highlighted focus player, a live HUD and a pitch minimap
   - analysis graphs + a player card
   - `report.html` (self-contained), `metrics.json`, `gemini_events.json`

## Quick start

```bash
uv sync                                     # Python 3.11 + CUDA torch, pinned in uv.lock
copy .env.example .env                      # then set GEMINI_API_KEY
uv run python scripts/download_models.py    # football player detector (~1.5 GB) + ball + pitch models (add --samples for demo clips)
uv run python main.py                       # interactive: asks for the video, team and player
```

Non-interactive:

```bash
uv run python main.py --video data/samples/0bfacc_0.mp4 --team 1 --player 3 --jersey 10 --name "Musiala"
uv run python main.py --video match.mp4 --team 2 --player all     # whole-team analysis
uv run python main.py --video match.mp4 --no-gemini               # tracking-only metrics
```

Team/player numbers match the contact sheets the tool generates (it opens them for you in interactive mode).
Tracking is cached, so analysing a different player of the same video only takes the analysis + rendering time.

## Web API (FastAPI + MongoDB)

```bash
uv run uvicorn app.main:app --port 8000      # docs at http://localhost:8000/docs
```

Needs `MONGODB_URL`, `MONGODB_DB_NAME` and `JWT_SECRET_KEY` in `.env` (the company dev Mongo requires the VPN;
`/api/v1/health` reports `database: ok | unreachable`). Collections: `users`, `videos`, `analyses`.

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/signup` · `POST /auth/login` · `GET /auth/me` | Argon2-hashed accounts, JWT bearer tokens |
| `POST /api/v1/videos` (multipart) | upload → metadata + thumbnail → **team/player detection starts automatically** |
| `GET /api/v1/videos` · `GET/DELETE /videos/{id}` | library (owner-scoped); video shows live `progress` and detected `teams` with player thumbnails |
| `POST /api/v1/videos/{id}/prepare` | retry detection after a failure |
| `POST /api/v1/videos/{id}/analyses` | queue a team or single-player analysis (`team`, `player`, `jersey_number`, `player_name`, `use_gemini`, `render_video`) |
| `GET /api/v1/analyses` · `GET/DELETE /analyses/{id}` | live stage progress while running; full metrics, Gemini events and artefact URLs when completed |
| `GET /outputs/...` | generated artefacts (thumbnails, annotated video, charts, reports) |

Jobs run in an in-process single-worker queue (the 4 GB GPU fits one job at a time) and write progress to Mongo;
jobs interrupted by a server restart are marked failed on startup. No Celery/Redis by design (MVP).

## Architecture

```
main.py                          CLI entry point
config/config.yaml               every tunable (models, thresholds, zones, Gemini, rendering)
config/botsort_football.yaml     alternative: BoT-SORT + YOLO26 ReID + camera-motion compensation
config/tracktrack_rfdetr.yaml    TrackTrack (CVPR 2025) + ReID on RF-DETR boxes (default)
config/tracktrack_football.yaml  TrackTrack + ReID for `detector.type: pose`
config/bytetrack_football.yaml   legacy: ByteTrack, no ReID
.env                             secrets only (GEMINI_API_KEY)
scripts/download_models.py       football-specific weights from roboflow/sports (MIT)
app/core/                        typed YAML config (app_config.py) + env settings (config.py)
app/engine/
  domain/        dataclasses shared by all stages (observations, tracks, targets) + COCO keypoint layout
  io/            VideoReader (stride / duration cap), VideoWriter (H.264 via bundled ffmpeg)
  cache/         StageCache — pass-1 results keyed by video content + config
  detection/     FootballTracker (RF-DETR -> TrackTrack/ReID -> CropPoseEstimator), PoseTracker (pose-only mode), ReIdEmbedder (YOLO26 ReID, 512-d),
                 BallDetector + trajectory filter/interpolation,
                 PitchKeypointDetector (automatic per-frame pitch homography)
  motion/        CameraMotionEstimator — Lucas-Kanade optical flow, scene-cut (replay) detection
  teams/         ShirtColorExtractor (pose torso polygon, grass removed) + TeamClassifier (KMeans, outliers)
  tracking/      TrackStitcher — re-links fragments by motion, kit colour and ReID appearance (separates
                 same-kit team-mates; re-links players re-entering the shot within 10 s)
  geometry/      ViewTransformer — manual homography > pitch keypoints > pose-height scale
  metrics/       KinematicsAnalyzer, PossessionAnalyzer, PoseMetricsAnalyzer
  gemini/        GeminiAgenticAnalyst (MediaProcessing.AGENTIC), prompts, structured event schema
  fusion/        EventCounts, RatingModel (FC-style attributes), ReportBuilder
  interactive/   contact sheets + team/player selection (interactive or preset)
  render/        VideoAnnotator, MatchVideoRenderer, Minimap, palette
  reports/       ChartFactory (matplotlib + mplsoccer), PlayerCardRenderer, HTML report, JSON serializer
  pipeline/      MatchAnalysisPipeline — prepare() (pass 1) + analyze() (pass 2)
app/api, app/services            FastAPI layer reusing the same pipeline
tests/                           unit tests for the pure logic
```

## How the numbers are produced

| Metric | Source |
|---|---|
| Distance, speed, speed zones, sprints, accelerations | tracked foot keypoints → metres (pitch homography or pose-height scale), Savitzky-Golay smoothed |
| Ball possession / touches | ball within ~0.55 body heights of a player's ankle keypoints, with hysteresis |
| Running cadence, trunk lean | ankle oscillation and shoulder-hip angle from the 17 pose keypoints |
| Passes, dribbles, shots, tackles, duels, interceptions, crosses, fouls… | Gemini agentic event log (timestamped, with success flags and confidence) |
| Event map | Gemini timestamps fused with the tracked player position at that moment |
| PAC/PHY | tracking; SHO/PAS/DRI/DEF from event rates shrunk toward typical values; OVR weighted by position |

## Player detection modes

`detector.type` in `config/config.yaml`:

- `rfdetr` (default): RF-DETR (SoccerNet) finds players, goalkeepers, referees and the ball; YOLO26n-pose runs top-down on
  each tracked player's crop. Much higher recall on small/distant players and explicit referee/goalkeeper roles.
  The checkpoint is large (RF-DETR-Large); if it runs out of GPU memory or is too slow, switch to `pose`.
- `pose`: the earlier single-model path (YOLO26n-pose on the whole frame at `pose.imgsz`).

Changing the detector changes the tracking signature: videos detected before need **Re-run detection** in the web app.
The SoccerNet checkpoint is trained on research-licensed data; check the licence before commercial use.

## Configuration notes

- `video.frame_stride: 2` halves processing time; `video.max_seconds` analyses only the start of a long video.
- If the pitch model cannot see enough landmarks (close-ups, unusual angles) the engine falls back to pose-height scaling automatically — the report states which geometry was used.
- A manual 4-point calibration (`geometry.calibration`) overrides automatic calibration for fixed tactical cameras.
- `uv run pytest` runs the unit tests.

Credits: football ball/pitch models and pitch landmark layout from [roboflow/sports](https://github.com/roboflow/sports) (MIT). Architecture pattern (YOLO + ByteTrack + KMeans teams + optical-flow camera compensation + homography) is common to open-source football analytics projects.
