# Graph Report - football_analysis  (2026-11-08)

## Corpus Check
- 150 files · ~53,764 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 5, .example 2, .css 2)

## Summary
- 1325 nodes · 3931 edges · 86 communities (52 shown, 34 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 325 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- EventCounts
- ChartFactory
- AnalysisDetail.jsx
- backend/main.py
- MatchAnalysisPipeline
- auth_service.py
- agentic_analyst.py
- App.jsx
- VideoDetail.jsx
- app/main.py
- analysis_service.py
- video_service.py
- PlayerTrack
- Motion.jsx
- package.json
- PlayerObservation
- match_analysis_pipeline.py
- Backend — ScoutAI
- Upload.jsx
- numpy
- team_classifier.py
- ViewTransformer
- CameraMotion
- app_config.py
- JobProgress
- AnalysisRepository
- VideoRepository
- FootballTracker
- ReIdConfig
- pathlib
- BallObservation
- VideoAnnotator
- config.yaml
- AnalysisCard.jsx
- kinematics
- observation
- local_storage.py
- pitch_detector.py
- ThumbnailCollector
- detector
- test_reid_stitching.py
- palette.py
- CameraMotionEstimator
- test_team_classifier.py
- RfDetrFootballDetector
- VideoInfo
- VideoWriter
- pitch
- pose
- PoseMetricsAnalyzer
- gemini
- MinimapRenderer
- ball
- geometry
- reid
- camera_motion
- rendering
- teams
- download_models.py
- presence
- stitching
- ScoutAI
- .claude/CLAUDE.md
- football-analysis-backend

## God Nodes (most connected - your core abstractions)
1. `MatchAnalysisPipeline` - 70 edges
2. `PlayerObservation` - 65 edges
3. `PlayerTrack` - 44 edges
4. `ViewTransformer` - 37 edges
5. `PlayerResult()` - 37 edges
6. `TeamResult()` - 32 edges
7. `MatchVideoRenderer` - 30 edges
8. `VideoDetail()` - 30 edges
9. `ChartFactory` - 29 edges
10. `BallObservation` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Frontend (`frontend/src`)` --references--> `cleanText()`  [INFERRED]
  docs/ARCHITECTURE.md → frontend/src/utils/format.js
- `Engine pipeline (`backend/app/engine/pipeline/match_analysis_pipeline.py`)` --references--> `BallTrajectoryBuilder`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/engine/detection/ball_detector.py
- `Flow` --references--> `MatchAnalysisPipeline`  [INFERRED]
  docs/ARCHITECTURE.md → backend/app/engine/pipeline/match_analysis_pipeline.py
- `Web API (FastAPI + MongoDB)` --references--> `player()`  [INFERRED]
  backend/README.md → backend/tests/factories.py
- `start_analysis()` --uses--> `AnalysisCreate`  [INFERRED]
  backend/app/api/v1/endpoints/videos.py → backend/app/schemas/analysis.py

## Import Cycles
- None detected.

## Communities (86 total, 34 thin omitted)

### Community 0 - "EventCounts"
Cohesion: 0.06
Nodes (32): KinematicsConfig, EventCounts, FifaRatings, RatingModel, _scale(), _shrunk_rate(), Confidence, EventType (+24 more)

### Community 1 - "ChartFactory"
Cohesion: 0.08
Nodes (10): PlayerReport, TeamReport, bgr_to_hex(), ChartFactory, _gaussian_blur(), _b64(), HtmlReportWriter, PlayerCardRenderer (+2 more)

### Community 2 - "AnalysisDetail.jsx"
Cohesion: 0.15
Nodes (51): GEOMETRY_TEXT, Methodology(), Section(), ATTRIBUTES, BulletList(), Caveats(), ChartGrid(), CONFIDENCE_TONE (+43 more)

### Community 3 - "backend/main.py"
Cohesion: 0.08
Nodes (13): configure_logging(), ContactSheetBuilder, _default_label(), InteractiveTargetSelector, open_file(), PresetTargetSelector, SelectionContext, ai_status() (+5 more)

### Community 4 - "MatchAnalysisPipeline"
Cohesion: 0.08
Nodes (13): ReIdEmbedder, TrackingResult, TargetSelector, VideoReader, AnalysisOutputs, MatchAnalysisPipeline, PreparedMatch, Architecture (+5 more)

### Community 5 - "auth_service.py"
Cohesion: 0.10
Nodes (17): login(), me(), signup(), Settings, create_access_token(), decode_access_token(), hash_password(), verify_password() (+9 more)

### Community 6 - "agentic_analyst.py"
Cohesion: 0.11
Nodes (9): StageCache, GeminiAgenticAnalyst, build_prompt(), GeminiTargetContext, _mmss(), _player_output(), _player_target(), _team_output() (+1 more)

### Community 7 - "App.jsx"
Cohesion: 0.14
Nodes (22): App(), AppNotFound(), NotFound(), Background(), AppShell(), NAV, Brand(), PRODUCT_NAME (+14 more)

### Community 8 - "VideoDetail.jsx"
Cohesion: 0.22
Nodes (29): Stagger(), StaggerItem(), EmptyState(), Kpi(), Toggle(), ConnectionBanner(), ErrorState(), LoadError() (+21 more)

### Community 9 - "app/main.py"
Cohesion: 0.10
Nodes (8): get_current_user(), get_db(), health_check(), ensure_indexes(), get_client(), get_database(), ping(), lifespan()

### Community 10 - "analysis_service.py"
Cohesion: 0.18
Nodes (18): delete_analysis(), get_analysis(), list_recent(), list_video_analyses(), AnalysisCreate, AnalysisDetail, AnalysisOut, AnalysisResult (+10 more)

### Community 11 - "video_service.py"
Cohesion: 0.17
Nodes (16): delete_video(), get_video(), list_videos(), retry_detection(), start_analysis(), upload_video(), VideoOut, get_video() (+8 more)

### Community 12 - "PlayerTrack"
Cohesion: 0.19
Nodes (8): AnalysisTarget, PlayerTrack, TeamAssignment, PlayerMetrics, MatchVideoRenderer, DrawnPlayer, FrameOverlay, HudStats

### Community 13 - "Motion.jsx"
Cohesion: 0.12
Nodes (25): ORDER, STAGES, StageTracker(), AnimatedHeadline(), CountUp(), EASE, Reveal(), ScanFrame() (+17 more)

### Community 14 - "package.json"
Cohesion: 0.09
Nodes (26): dependencies, axios@^1.7.7, lucide-react@^0.460.0, motion@^12.43.0, react@^18.3.1, react-dom@^18.3.1, react-router-dom@^6.26.2, devDependencies (+18 more)

### Community 15 - "PlayerObservation"
Cohesion: 0.14
Nodes (4): PlayerObservation, ShirtColorExtractor, grass_mask(), PitchPresenceFilter

### Community 16 - "match_analysis_pipeline.py"
Cohesion: 0.16
Nodes (9): MatchReport, ReportBuilder, GeminiMatchAnalysis, PoseProfile, PossessionTimeline, _visible_windows(), player_to_dict(), report_to_dict() (+1 more)

### Community 17 - "Backend — ScoutAI"
Cohesion: 0.08
Nodes (22): Architecture, Backend — ScoutAI, Configuration notes, How the numbers are produced, Player detection modes, Quick start, Web API (FastAPI + MongoDB), Code conventions (+14 more)

### Community 18 - "Upload.jsx"
Cohesion: 0.12
Nodes (22): BackButton(), Topbar(), AuthContext, AuthProvider(), SESSION_EXPIRED, ACCEPT, extensionOf(), EXTENSIONS (+14 more)

### Community 20 - "team_classifier.py"
Cohesion: 0.17
Nodes (7): track_role(), _nearest_team_by_position(), _outfield(), _rolling_majority(), shirt_feature(), _team_positions_by_frame(), TeamClassifier

### Community 22 - "CameraMotion"
Cohesion: 0.19
Nodes (10): StitchingConfig, CameraMotion, _cosine_distance(), _Fragment, TrackStitcher, _fragment(), _teams(), test_different_teams_or_far_positions_stay_separate() (+2 more)

### Community 23 - "app_config.py"
Cohesion: 0.19
Nodes (13): AppConfig, BallConfig, GeminiConfig, get_app_config(), load_app_config(), PathsConfig, PoseMetricsConfig, PossessionConfig (+5 more)

### Community 24 - "JobProgress"
Cohesion: 0.15
Nodes (6): JobProgress, PlayerOption, TeamOption, StageProgress, submit(), _team_options()

### Community 25 - "AnalysisRepository"
Cohesion: 0.13
Nodes (4): AnalysisRepository, _headline(), _run_job(), delete_video()

### Community 26 - "VideoRepository"
Cohesion: 0.12
Nodes (5): VideoRepository, public_error(), build_pipeline(), current_tracking_signature(), _prepare_job()

### Community 27 - "FootballTracker"
Cohesion: 0.19
Nodes (4): DetectorConfig, PoseConfig, CropPoseEstimator, FootballTracker

### Community 28 - "ReIdConfig"
Cohesion: 0.19
Nodes (4): ReIdConfig, PoseTracker, resolve_tracker_config(), reid_model_path()

### Community 30 - "BallObservation"
Cohesion: 0.20
Nodes (5): BallDetector, BallTrajectoryBuilder, BallObservation, PossessionAnalyzer, PossessionSpell

### Community 32 - "config.yaml"
Cohesion: 0.12
Nodes (15): paths, cache_dir, models_dir, output_root, pose_metrics, min_speed_kmh_for_cadence, possession, control_radius_body_heights (+7 more)

### Community 33 - "AnalysisCard.jsx"
Cohesion: 0.35
Nodes (13): AnalysisCard(), Headline(), ChartFigure(), spotlightHandlers(), VideoCard(), ProgressBar(), isActive(), STATUS (+5 more)

### Community 34 - "kinematics"
Cohesion: 0.13
Nodes (15): kinematics, acceleration_min_duration_s, acceleration_threshold_ms2, max_gap_seconds, max_speed_kmh, smoothing_seconds, speed_zones_kmh, sprint_min_duration_s (+7 more)

### Community 35 - "observation"
Cohesion: 0.26
Nodes (7): CalibrationConfig, GeometryConfig, observation(), player(), test_homography_maps_calibration_square_to_metres(), test_pose_scale_uses_player_height_as_ruler(), test_runs_break_on_long_gaps()

### Community 36 - "local_storage.py"
Cohesion: 0.25
Nodes (7): delete_video_files(), outputs_root(), public_url(), save_upload(), upload_dir(), UploadTooLarge, video_output_dir()

### Community 37 - "pitch_detector.py"
Cohesion: 0.21
Nodes (3): PitchConfig, PitchKeypointDetector, pitch_keypoints()

### Community 38 - "ThumbnailCollector"
Cohesion: 0.26
Nodes (5): _crop(), _max_iou(), pick_thumbnail(), score(), ThumbnailCollector

### Community 39 - "detector"
Cohesion: 0.17
Nodes (12): detector, ball_candidates, ball_threshold, checkpoint, class_names, pose_batch_size, pose_crop_imgsz, pose_crop_margin (+4 more)

### Community 40 - "test_reid_stitching.py"
Cohesion: 0.29
Nodes (7): appearance(), _fragment(), _stitch(), _teams(), test_long_gaps_need_appearance_evidence(), test_reid_keeps_same_kit_team_mates_apart(), test_reid_relinks_a_player_after_a_long_absence()

### Community 41 - "palette.py"
Cohesion: 0.29
Nodes (4): describe_color(), ensure_visible(), lab_to_bgr(), readable_text_color()

### Community 43 - "test_team_classifier.py"
Cohesion: 0.40
Nodes (8): TeamsConfig, _fitted(), _role_track(), test_banded_white_kit_and_numbered_red_kit_are_separated_and_referee_is_other(), test_detected_referee_is_other_even_in_a_team_coloured_kit(), test_goalkeeper_joins_the_team_standing_nearest_to_him(), test_track_that_swaps_to_an_opponent_is_split(), _track()

### Community 47 - "pitch"
Cohesion: 0.20
Nodes (10): pitch, conf, enabled, every_n_frames, imgsz, keypoint_conf, min_coverage, min_keypoints (+2 more)

### Community 48 - "pose"
Cohesion: 0.20
Nodes (10): pose, conf, device, half, imgsz, iou, min_box_height_px, min_keypoint_conf (+2 more)

### Community 50 - "gemini"
Cohesion: 0.22
Nodes (9): gemini, agentic, enabled, fallback_fps, file_poll_interval_s, file_poll_timeout_s, model, prompt_version (+1 more)

### Community 53 - "ball"
Cohesion: 0.25
Nodes (8): ball, class_names, conf, fallback_model, imgsz, max_interpolation_gap, max_jump_px_per_frame, model

### Community 54 - "geometry"
Cohesion: 0.25
Nodes (8): image_points, pitch_points, geometry, calibration, mode, pitch_length_m, pitch_width_m, reference_height_m

### Community 55 - "reid"
Cohesion: 0.25
Nodes (8): reid, edge_embeddings, enabled, long_gap_max_distance, long_gap_seconds, max_link_distance, model, sample_every_n_frames

### Community 56 - "camera_motion"
Cohesion: 0.29
Nodes (7): camera_motion, downscale, enabled, max_corners, min_distance, min_inlier_ratio, quality_level

### Community 57 - "rendering"
Cohesion: 0.29
Nodes (7): rendering, hud, label_track_ids, minimap, skeleton_all_players, trail_length, transcode_h264

### Community 58 - "teams"
Cohesion: 0.29
Nodes (7): teams, goalkeepers_by_position, max_samples_per_track, min_track_observations, n_teams, outlier_distance_factor, switch_min_observations

### Community 59 - "download_models.py"
Cohesion: 0.48
Nodes (3): download(), fetch(), main()

### Community 60 - "presence"
Cohesion: 0.40
Nodes (5): presence, min_grass_fraction, min_track_on_grass, min_track_on_pitch, pitch_margin_m

### Community 61 - "stitching"
Cohesion: 0.40
Nodes (5): stitching, base_radius_px, max_gap_seconds, max_shirt_distance, max_speed_px_per_frame

### Community 62 - "ScoutAI"
Cohesion: 0.50
Nodes (3): Run the analysis from the command line, Run the web app (2 terminals, VPN on for the dev MongoDB), ScoutAI

## Knowledge Gaps
- **1 isolated node(s):** `football-analysis-backend`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 408 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MatchAnalysisPipeline` connect `MatchAnalysisPipeline` to `EventCounts`, `ChartFactory`, `backend/main.py`, `agentic_analyst.py`, `video_service.py`, `PlayerTrack`, `PlayerObservation`, `match_analysis_pipeline.py`, `team_classifier.py`, `ViewTransformer`, `CameraMotion`, `app_config.py`, `VideoRepository`, `FootballTracker`, `ReIdConfig`, `BallObservation`, `VideoAnnotator`, `pitch_detector.py`, `ThumbnailCollector`, `CameraMotionEstimator`, `PoseMetricsAnalyzer`, `MinimapRenderer`?**
  _High betweenness centrality (0.301) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `MatchAnalysisPipeline` (e.g. with `AppConfig` and `StageCache`) actually correct?**
  _`MatchAnalysisPipeline` has 42 INFERRED edges - model-reasoned connections that need verification._
- **What connects `football-analysis-backend` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `EventCounts` be split into smaller, more focused modules?**
  _Cohesion score 0.06219918548685672 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `MatchAnalysisPipeline` to `Backend — ScoutAI`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `PlayerObservation` (e.g. with `FootballTracker` and `PoseTracker`) actually correct?**
  _`PlayerObservation` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Should `ChartFactory` be split into smaller, more focused modules?**
  _Cohesion score 0.07738095238095238 - nodes in this community are weakly interconnected._