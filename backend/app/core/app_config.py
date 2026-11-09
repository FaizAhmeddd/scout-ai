from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = BACKEND_ROOT / "config" / "config.yaml"


class PathsConfig(BaseModel):
    output_root: Path = Path("outputs")
    cache_dir: Path = Path(".cache/stages")
    models_dir: Path = Path("data/models")


class VideoConfig(BaseModel):
    frame_stride: int = Field(default=1, ge=1)
    max_seconds: float | None = None


class PoseConfig(BaseModel):
    model: str = "yolo26n-pose.pt"
    device: str = "auto"
    half: bool = True
    imgsz: int = 3840
    conf: float = 0.25
    iou: float = 0.5
    tracker: Path = Path("config/tracktrack_football.yaml")
    min_keypoint_conf: float = 0.35
    min_box_height_px: float = 18


class DetectorConfig(BaseModel):
    type: Literal["rfdetr", "pose"] = "rfdetr"
    checkpoint: str = "rfdetr-soccernet/checkpoint_best_regular.pth"
    resolution: int = Field(default=896, gt=0)
    threshold: float = 0.3
    class_names: list[str] = ["ball", "player", "referee", "goalkeeper"]
    tracker: Path = Path("config/tracktrack_rfdetr.yaml")
    ball_candidates: bool = True
    ball_threshold: float = 0.35
    pose_crop_imgsz: int = 256
    pose_crop_margin: float = 0.15
    pose_batch_size: int = 32


class BallConfig(BaseModel):
    model: str = "football-ball-detection.pt"
    fallback_model: str = "yolo26s.pt"
    class_names: list[str] = ["ball", "football", "sports ball"]
    imgsz: int = 1280
    conf: float = 0.15
    max_jump_px_per_frame: float = 60
    max_interpolation_gap: int = 25


class PitchConfig(BaseModel):
    enabled: bool = True
    model: str = "football-pitch-detection.pt"
    imgsz: int = 640
    conf: float = 0.3
    keypoint_conf: float = 0.5
    min_keypoints: int = 4
    every_n_frames: int = Field(default=2, ge=1)
    min_coverage: float = 0.4
    smoothing_window: int = 5


class PresenceConfig(BaseModel):
    min_grass_fraction: float = 0.3
    min_track_on_grass: float = 0.6
    pitch_margin_m: float = 2.0
    min_track_on_pitch: float = 0.6


class TeamsConfig(BaseModel):
    n_teams: int = 2
    min_track_observations: int = 8
    max_samples_per_track: int = 40
    outlier_distance_factor: float = 2.2
    switch_min_observations: int = 12
    goalkeepers_by_position: bool = True


class ReIdConfig(BaseModel):
    enabled: bool = True
    model: str = "yolo26s-reid.onnx"
    sample_every_n_frames: int = Field(default=3, ge=1)
    edge_embeddings: int = Field(default=8, ge=1)
    max_link_distance: float = 0.35
    long_gap_seconds: float = 10.0
    long_gap_max_distance: float = 0.22


class StitchingConfig(BaseModel):
    max_gap_seconds: float = 3.0
    max_speed_px_per_frame: float = 14.0
    base_radius_px: float = 40.0
    max_shirt_distance: float = 0.45


class CameraMotionConfig(BaseModel):
    enabled: bool = True
    max_corners: int = 300
    quality_level: float = 0.01
    min_distance: int = 10
    min_inlier_ratio: float = 0.35
    downscale: float = 0.5


class CalibrationConfig(BaseModel):
    image_points: list[list[float]] | None = None
    pitch_points: list[list[float]] | None = None

    @model_validator(mode="after")
    def _check_pairs(self) -> "CalibrationConfig":
        if (self.image_points is None) != (self.pitch_points is None):
            raise ValueError("calibration.image_points and calibration.pitch_points must be set together")
        if self.image_points is not None:
            if len(self.image_points) != len(self.pitch_points) or len(self.image_points) < 4:
                raise ValueError("calibration needs at least 4 matching image/pitch points")
        return self

    @property
    def is_set(self) -> bool:
        return self.image_points is not None


class GeometryConfig(BaseModel):
    mode: str = "auto"
    reference_height_m: float = 1.75
    pitch_length_m: float = 105.0
    pitch_width_m: float = 68.0
    calibration: CalibrationConfig = CalibrationConfig()


class KinematicsConfig(BaseModel):
    smoothing_seconds: float = 0.6
    top_speed_window_s: float = 1.0
    max_speed_kmh: float = 38.0
    max_gap_seconds: float = 0.6
    speed_zones_kmh: dict[str, tuple[float, float]] = {
        "walking": (0, 7),
        "jogging": (7, 15),
        "running": (15, 20),
        "high_speed": (20, 25),
        "sprinting": (25, 99),
    }
    sprint_threshold_kmh: float = 25.0
    sprint_min_duration_s: float = 1.0
    acceleration_threshold_ms2: float = 3.0
    acceleration_min_duration_s: float = 0.5


class PossessionConfig(BaseModel):
    control_radius_body_heights: float = 0.55
    min_consecutive_frames: int = 3


class PoseMetricsConfig(BaseModel):
    min_speed_kmh_for_cadence: float = 9.0


class GeminiConfig(BaseModel):
    enabled: bool = True
    model: str = "gemini-3.7-flash"
    agentic: bool = True
    fallback_fps: float = 2.0
    temperature: float = 0.2
    file_poll_interval_s: float = 3.0
    file_poll_timeout_s: float = 900.0
    prompt_version: str = "v2"


class RenderingConfig(BaseModel):
    skeleton_all_players: bool = True
    trail_length: int = 45
    hud: bool = True
    minimap: bool = True
    label_track_ids: bool = True
    transcode_h264: bool = True


class ReportConfig(BaseModel):
    dpi: int = 150
    open_when_done: bool = True


class AppConfig(BaseModel):
    paths: PathsConfig = PathsConfig()
    video: VideoConfig = VideoConfig()
    detector: DetectorConfig = DetectorConfig()
    pose: PoseConfig = PoseConfig()
    ball: BallConfig = BallConfig()
    pitch: PitchConfig = PitchConfig()
    presence: PresenceConfig = PresenceConfig()
    teams: TeamsConfig = TeamsConfig()
    reid: ReIdConfig = ReIdConfig()
    stitching: StitchingConfig = StitchingConfig()
    camera_motion: CameraMotionConfig = CameraMotionConfig()
    geometry: GeometryConfig = GeometryConfig()
    kinematics: KinematicsConfig = KinematicsConfig()
    possession: PossessionConfig = PossessionConfig()
    pose_metrics: PoseMetricsConfig = PoseMetricsConfig()
    gemini: GeminiConfig = GeminiConfig()
    rendering: RenderingConfig = RenderingConfig()
    report: ReportConfig = ReportConfig()

    def resolve(self, path: Path) -> Path:
        """Resolves a config-relative path against the backend root."""
        return path if path.is_absolute() else BACKEND_ROOT / path


def load_app_config(path: Path | str | None = None) -> AppConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return AppConfig.model_validate(raw)


@lru_cache
def get_app_config() -> AppConfig:
    return load_app_config()
