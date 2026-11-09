from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

from app.core.app_config import KinematicsConfig
from app.engine.geometry.view_transformer import PositionSeries

KMH_PER_MS = 3.6
_OUTLIER_FILTER_S = 0.3
_TELEPORT_FACTOR = 1.3


@dataclass
class Sprint:
    start_s: float
    end_s: float
    peak_kmh: float
    distance_m: float


@dataclass
class KinematicProfile:
    seconds: np.ndarray
    speed_kmh: np.ndarray
    cumulative_distance_m: np.ndarray
    sustained_speed_kmh: np.ndarray = field(default_factory=lambda: np.zeros(0))  # 1 s rolling mean
    total_distance_m: float = 0.0
    distance_by_zone_m: dict[str, float] = field(default_factory=dict)
    top_speed_kmh: float = 0.0
    time_tracked_s: float = 0.0
    sprints: list[Sprint] = field(default_factory=list)
    accelerations: int = 0
    decelerations: int = 0

    @property
    def avg_speed_kmh(self) -> float:
        return self.total_distance_m / self.time_tracked_s * KMH_PER_MS if self.time_tracked_s else 0.0

    @property
    def distance_per_min(self) -> float:
        return self.total_distance_m / (self.time_tracked_s / 60) if self.time_tracked_s else 0.0

    @property
    def high_intensity_distance_m(self) -> float:
        return self.distance_by_zone_m.get("high_speed", 0.0) + self.distance_by_zone_m.get("sprinting", 0.0)

    def speed_at(self, seconds: float) -> float | None:
        if not len(self.seconds):
            return None
        i = int(np.argmin(np.abs(self.seconds - seconds)))
        value = self.speed_kmh[i]
        return None if np.isnan(value) or abs(self.seconds[i] - seconds) > 0.5 else float(value)

    def distance_until(self, seconds: float) -> float:
        if not len(self.seconds):
            return 0.0
        i = int(np.searchsorted(self.seconds, seconds, side="right")) - 1
        return float(self.cumulative_distance_m[i]) if i >= 0 else 0.0


class KinematicsAnalyzer:
    """Physical output from a metric trajectory: distance, speed zones, sprints, accelerations."""

    def __init__(self, config: KinematicsConfig):
        self.config = config

    def analyze(self, series: PositionSeries) -> KinematicProfile:
        n = len(series)
        speed = np.full(n, np.nan)
        sustained = np.zeros(n)
        step_distance = np.zeros(n)
        profile = KinematicProfile(
            seconds=series.seconds,
            speed_kmh=speed,
            cumulative_distance_m=np.zeros(n),
            sustained_speed_kmh=sustained,
            distance_by_zone_m={zone: 0.0 for zone in self.config.speed_zones_kmh},
        )

        for idx in self._continuous_segments(series):
            if len(idx) < 3:
                continue
            t = series.seconds[idx]
            step_s = float(np.median(np.diff(t)))
            if t[-1] - t[0] < self.config.smoothing_seconds:
                continue  # too short to smooth reliably; would only contribute noise
            xy = self._smooth(series.xy_m[idx], step_s)
            run_speed = np.linalg.norm(np.gradient(xy, t, axis=0), axis=1) * KMH_PER_MS
            run_speed[run_speed > self.config.max_speed_kmh] = np.nan
            speed[idx] = run_speed
            sustained[idx] = self._sustained(run_speed, step_s)

            steps = np.linalg.norm(np.diff(xy, axis=0), axis=1)
            step_speed = steps / np.maximum(np.diff(t), 1e-6) * KMH_PER_MS
            valid = step_speed <= self.config.max_speed_kmh
            step_distance[idx[1:]] = np.where(valid, steps, 0.0)
            for d, s in zip(steps[valid], step_speed[valid]):
                profile.distance_by_zone_m[self._zone(s)] += float(d)

            profile.time_tracked_s += float(t[-1] - t[0])
            profile.sprints.extend(self._sprints(t, run_speed, steps))
            acc, dec = self._accelerations(t, run_speed)
            profile.accelerations += acc
            profile.decelerations += dec

        profile.cumulative_distance_m = np.cumsum(step_distance)
        profile.total_distance_m = float(step_distance.sum())
        profile.top_speed_kmh = float(sustained.max()) if n else 0.0
        return profile

    def _continuous_segments(self, series: PositionSeries) -> list[np.ndarray]:
        """Runs further split wherever the position jumps faster than any human can run.

        Such teleports are identity swaps between team-mates or calibration jumps; measuring across them
        would invent distance and speed.
        """
        segments = []
        for idx in series.runs():
            if len(idx) < 2:
                segments.append(idx)
                continue
            raw_xy = series.xy_m[idx]
            if len(idx) >= 3:
                raw_xy = median_filter(raw_xy, size=(3, 1), mode="nearest")
            step_speed = (
                np.linalg.norm(np.diff(raw_xy, axis=0), axis=1)
                / np.maximum(np.diff(series.seconds[idx]), 1e-6)
                * KMH_PER_MS
            )
            cuts = np.flatnonzero(step_speed > _TELEPORT_FACTOR * self.config.max_speed_kmh) + 1
            segments.extend(np.split(idx, cuts))
        return segments

    def _smooth(self, xy: np.ndarray, step_s: float) -> np.ndarray:
        """Median filter removes isolated position outliers (calibration jumps), then Savitzky-Golay smooths."""
        median_window = max(int(round(_OUTLIER_FILTER_S / max(step_s, 1e-3))) | 1, 3)
        if len(xy) >= median_window:
            xy = median_filter(xy, size=(median_window, 1), mode="nearest")
        window = int(round(self.config.smoothing_seconds / max(step_s, 1e-3))) | 1
        window = min(window, len(xy) if len(xy) % 2 else len(xy) - 1)
        if window < 5:
            return xy
        return savgol_filter(xy, window_length=window, polyorder=2, axis=0, mode="nearest")

    def _sustained(self, speed: np.ndarray, step_s: float) -> np.ndarray:
        """Speed held over a short window, as tracking providers report top speed (single-frame spikes ignored)."""
        window = max(int(round(self.config.top_speed_window_s / max(step_s, 1e-3))), 1)
        if len(speed) < window:
            return np.zeros(len(speed))
        valid = np.isfinite(speed)
        kernel = np.ones(window)
        sums = np.convolve(np.where(valid, speed, 0.0), kernel, mode="same")
        counts = np.convolve(valid.astype(float), kernel, mode="same")
        return np.where(counts >= 0.8 * window, sums / np.maximum(counts, 1), 0.0)

    def _zone(self, speed_kmh: float) -> str:
        for zone, (low, high) in self.config.speed_zones_kmh.items():
            if low <= speed_kmh < high:
                return zone
        return next(reversed(self.config.speed_zones_kmh))

    def _sprints(self, t: np.ndarray, speed: np.ndarray, steps: np.ndarray) -> list[Sprint]:
        sprints = []
        for start, end in _true_runs(np.nan_to_num(speed) >= self.config.sprint_threshold_kmh):
            if t[end] - t[start] >= self.config.sprint_min_duration_s:
                sprints.append(
                    Sprint(
                        start_s=float(t[start]),
                        end_s=float(t[end]),
                        peak_kmh=float(np.nanmax(speed[start: end + 1])),
                        distance_m=float(steps[start:end].sum()),
                    )
                )
        return sprints

    def _accelerations(self, t: np.ndarray, speed_kmh: np.ndarray) -> tuple[int, int]:
        speed_ms = np.nan_to_num(speed_kmh) / KMH_PER_MS
        if len(speed_ms) < 3:
            return 0, 0
        accel = np.gradient(speed_ms, t)
        threshold = self.config.acceleration_threshold_ms2
        min_duration = self.config.acceleration_min_duration_s

        def count(mask: np.ndarray) -> int:
            return sum(1 for s, e in _true_runs(mask) if t[e] - t[s] >= min_duration)

        return count(accel >= threshold), count(accel <= -threshold)


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index pairs of consecutive True values."""
    runs, start = [], None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs
