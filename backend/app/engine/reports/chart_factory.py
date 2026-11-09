from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from mplsoccer import Pitch, Radar
from scipy.ndimage import gaussian_filter

from app.engine.fusion.rating_model import ATTRIBUTES
from app.engine.fusion.report_builder import MatchReport, PlayerReport, TeamReport
from app.engine.gemini.schemas import EventType
from app.engine.render.palette import EVENT_COLORS_HEX, bgr_to_hex, ensure_visible
from app.engine.reports import style

# Charts shown side by side in the web page share this size, so a row of them lines up.
_ROW_FIGSIZE = (12, 4.8)

_ZONE_LABELS = {
    "walking": "Walking",
    "jogging": "Jogging",
    "running": "Running",
    "high_speed": "High speed",
    "sprinting": "Sprinting",
}


class ChartFactory:
    """Builds the analysis graphs. Every method writes one PNG and returns its path (or None if no data)."""

    def __init__(self, output_dir: Path, dpi: int, pitch_length_m: float, pitch_width_m: float, zones_kmh: dict[str, tuple[float, float]]):
        self.output_dir = output_dir
        self.dpi = dpi
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self.zones_kmh = zones_kmh
        self.output_dir.mkdir(parents=True, exist_ok=True)
        style.apply_theme()

    # ------------------------------------------------------------------ player mode

    def player_charts(self, report: MatchReport) -> dict[str, Path]:
        player = report.focus_player
        builders = {
            "Attribute radar": lambda: self.attribute_radar(player),
            "Speed timeline": lambda: self.speed_timeline(player),
            "Distance by speed zone": lambda: self.speed_zones(player),
            "Work-rate profile": lambda: self.intensity_profile(player),
            "Heatmap": lambda: self.heatmap([player], report.pitch_coordinates, f"{player.label} - heatmap", "player_heatmap.png"),
            "Movement trail": lambda: self.movement_trail(player, report.pitch_coordinates),
            "Event timeline": lambda: self.event_timeline(player.events, f"{player.label} - match events", "player_event_timeline.png"),
            "Success rates": lambda: self.success_donuts(player),
            "Event map": lambda: self.event_map(player, report.pitch_coordinates),
        }
        return self._run(builders)

    def attribute_radar(self, player: PlayerReport) -> Path:
        values = [player.ratings.attributes[a] for a in ATTRIBUTES]
        radar = Radar(list(ATTRIBUTES), [30] * 6, [99] * 6, round_int=[True] * 6, num_rings=4, ring_width=1, center_circle_radius=1)
        fig, ax = radar.setup_axis(figsize=(7, 7), facecolor=style.BACKGROUND)
        ax.grid(False)
        radar.draw_circles(ax=ax, facecolor="#1A222D", edgecolor=style.GRID, lw=1.2)
        radar.draw_radar(values, ax=ax, kwargs_radar={"facecolor": style.ACCENT, "alpha": 0.6, "edgecolor": style.ACCENT},
                         kwargs_rings={"facecolor": "#7A6E00", "alpha": 0.55})
        radar.draw_range_labels(ax=ax, fontsize=9, color=style.MUTED)
        radar.draw_param_labels(ax=ax, fontsize=14, color=style.TEXT, fontweight="bold")
        fig.suptitle(f"{player.label}  |  OVR {player.ratings.overall}", color=style.TEXT, fontsize=16, fontweight="bold")
        return self._save(fig, "player_radar.png")

    def speed_timeline(self, player: PlayerReport) -> Path | None:
        kin = player.metrics.kinematics
        if not np.isfinite(kin.speed_kmh).any():
            return None
        fig, ax = plt.subplots(figsize=_ROW_FIGSIZE)
        for zone, (low, high) in self.zones_kmh.items():
            ax.axhspan(low, min(high, 40), color=style.ZONE_COLORS.get(zone, style.GRID), alpha=0.07)
        for sprint in kin.sprints:
            ax.axvspan(sprint.start_s, sprint.end_s, color=style.FAILURE, alpha=0.25)
        gaps = np.flatnonzero(np.diff(kin.seconds) > 0.5) + 1
        ax.plot(np.insert(kin.seconds, gaps, np.nan), np.insert(kin.speed_kmh, gaps, np.nan), color=style.ACCENT, linewidth=1.6)
        ax.axhline(kin.top_speed_kmh, color=style.FAILURE, linestyle="--", linewidth=1.2,
                   label=f"Top speed (sustained 1 s): {kin.top_speed_kmh:.1f} km/h")
        ax.legend(loc="upper right")
        ax.set_xlabel("Video time (s)")
        ax.set_ylabel("Speed (km/h)")
        ax.set_ylim(0, max(30, kin.top_speed_kmh + 4))
        ax.set_title(f"Speed profile  -  {len(kin.sprints)} sprints (shaded), avg {kin.avg_speed_kmh:.1f} km/h")
        return self._save(fig, "player_speed_timeline.png")

    def speed_zones(self, player: PlayerReport) -> Path:
        zones = player.metrics.kinematics.distance_by_zone_m
        total = sum(zones.values()) or 1.0
        fig, ax = plt.subplots(figsize=_ROW_FIGSIZE)
        names = list(zones)
        bars = ax.barh([_ZONE_LABELS.get(z, z) for z in names], [zones[z] for z in names],
                       color=[style.ZONE_COLORS.get(z, style.ACCENT) for z in names])
        for bar, zone in zip(bars, names):
            ax.text(bar.get_width() + total * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{zones[zone]:.0f} m  ({zones[zone] / total * 100:.0f}%)", va="center", color=style.TEXT)
        ax.invert_yaxis()
        ax.set_xlabel("Distance (m)")
        ax.set_xlim(0, max(zones.values(), default=1) * 1.35 + 1)
        ax.set_title(f"Distance by intensity zone  -  total {player.metrics.kinematics.total_distance_m:.0f} m")
        return self._save(fig, "player_speed_zones.png")

    def intensity_profile(self, player: PlayerReport) -> Path | None:
        kin = player.metrics.kinematics
        if kin.time_tracked_s < 30:
            return None
        bin_s = 30
        edges = np.arange(0, kin.seconds[-1] + bin_s, bin_s)
        steps = np.diff(kin.cumulative_distance_m, prepend=0.0)
        per_bin = np.histogram(kin.seconds, bins=edges, weights=steps)[0]
        on_screen = np.histogram(kin.seconds, bins=edges)[0] > 0
        fig, ax = plt.subplots(figsize=_ROW_FIGSIZE)
        centers = (edges[:-1] + edges[1:]) / 2
        ax.bar(centers[on_screen], per_bin[on_screen] * (60 / bin_s), width=bin_s * 0.85, color=style.ACCENT, alpha=0.85)
        ax.axhline(kin.distance_per_min, color=style.FAILURE, linestyle="--", linewidth=1.2, label=f"Average {kin.distance_per_min:.0f} m/min")
        ax.set_xlabel("Video time (s)")
        ax.set_ylabel("Metres per minute")
        ax.set_title("Work-rate profile (30 s windows)")
        ax.legend()
        return self._save(fig, "player_workrate.png")

    def movement_trail(self, player: PlayerReport, on_pitch: bool) -> Path | None:
        series, kin = player.metrics.series, player.metrics.kinematics
        if len(series) < 5:
            return None
        fig, ax = self._map_axes(on_pitch, series.xy_m, figsize=(11, 7.5))
        speed = np.nan_to_num(kin.speed_kmh)
        norm = plt.Normalize(0, max(28, float(speed.max())))
        for idx in series.runs():
            if len(idx) < 2:
                continue
            points = series.xy_m[idx].reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            lines = LineCollection(segments, cmap="turbo", norm=norm, linewidth=2.4)
            lines.set_array(speed[idx][1:])
            ax.add_collection(lines)
        mappable = plt.cm.ScalarMappable(norm=norm, cmap="turbo")
        fig.colorbar(mappable, ax=ax, fraction=0.03, pad=0.02, label="Speed (km/h)")
        ax.set_title(f"{player.label} - movement trail coloured by speed", color=style.TEXT)
        return self._save(fig, "player_movement_trail.png")

    def success_donuts(self, player: PlayerReport) -> Path | None:
        c = player.counts
        if c is None:
            return None
        items = [
            ("Passes", c.passes_completed, c.passes_attempted),
            ("Dribbles", c.dribbles_successful, c.dribbles_attempted),
            ("Duels", c.duels_won, c.duels),
            ("Tackles", c.tackles_won, c.tackles_attempted),
            ("Shots on target", c.shots_on_target, c.shots),
        ]
        fig, axes = plt.subplots(1, len(items), figsize=_ROW_FIGSIZE)
        for ax, (name, won, total) in zip(axes, items):
            ax.set_facecolor(style.BACKGROUND)
            ax.grid(False)
            if total:
                ax.pie([won, total - won], colors=[style.SUCCESS, style.FAILURE], startangle=90, counterclock=False,
                       wedgeprops={"width": 0.32, "edgecolor": style.BACKGROUND})
                ax.text(0, 0, f"{won / total * 100:.0f}%", ha="center", va="center", fontsize=17, fontweight="bold")
            else:
                ax.pie([1], colors=[style.GRID], wedgeprops={"width": 0.32})
                ax.text(0, 0, "n/a", ha="center", va="center", fontsize=14, color=style.MUTED)
            ax.set_title(f"{name}\n{won}/{total}", fontsize=11)
        fig.suptitle("Success rates (AI event log)", fontweight="bold")
        return self._save(fig, "player_success_rates.png")

    def event_map(self, player: PlayerReport, on_pitch: bool) -> Path | None:
        located = [(e, xy) for e, xy in player.event_positions if xy is not None]
        if not located:
            return None
        fig, ax = self._map_axes(on_pitch, np.stack([xy for _, xy in located] + [player.metrics.series.xy_m.mean(axis=0)]), figsize=(11, 7.5))
        for event_type in sorted({e.event_type for e, _ in located}, key=lambda t: t.value):
            subset = [(e, xy) for e, xy in located if e.event_type == event_type]
            color = EVENT_COLORS_HEX.get(event_type.value, style.ACCENT)
            xs = [xy[0] for _, xy in subset]
            ys = [xy[1] for _, xy in subset]
            faces = [color if e.successful else "none" for e, _ in subset]
            ax.scatter(xs, ys, s=150, facecolors=faces, edgecolors=color, linewidths=2, label=event_type.value.replace("_", " "), zorder=4)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=9, title="filled = successful")
        ax.set_title(f"{player.label} - where actions happened (tracking + AI events)", color=style.TEXT)
        return self._save(fig, "player_event_map.png")

    # ------------------------------------------------------------------ shared

    def event_timeline(self, events, title: str, filename: str) -> Path | None:
        if not events:
            return None
        types = [t for t in EventType if any(e.event_type == t for e in events)]
        fig, ax = plt.subplots(figsize=(_ROW_FIGSIZE[0], max(0.55 * len(types) + 2, _ROW_FIGSIZE[1])))
        for row, event_type in enumerate(types):
            subset = [e for e in events if e.event_type == event_type]
            color = EVENT_COLORS_HEX.get(event_type.value, style.ACCENT)
            ax.scatter([e.timestamp_s for e in subset], [row] * len(subset), s=110,
                       facecolors=[color if e.successful else "none" for e in subset], edgecolors=color, linewidths=2, zorder=3)
        ax.set_yticks(range(len(types)), [f"{t.value.replace('_', ' ')} ({sum(e.event_type == t for e in events)})" for t in types])
        ax.set_xlabel("Video time (s)")
        ax.set_title(f"{title}  (filled = successful, hollow = unsuccessful)")
        ax.invert_yaxis()
        return self._save(fig, filename)

    def heatmap(self, players: list[PlayerReport], on_pitch: bool, title: str, filename: str) -> Path | None:
        points = [p.metrics.series.xy_m for p in players if len(p.metrics.series)]
        if not points or sum(len(p) for p in points) < 10:
            return None
        xy = np.concatenate(points)
        if on_pitch:
            pitch = Pitch(pitch_type="custom", pitch_length=self.pitch_length, pitch_width=self.pitch_width,
                          pitch_color=style.PANEL, line_color=style.MUTED, line_zorder=2)
            fig, ax = pitch.draw(figsize=(11, 7.5))
            stats = pitch.bin_statistic(xy[:, 0], xy[:, 1], statistic="count", bins=(24, 16), normalize=True)
            stats["statistic"] = _gaussian_blur(stats["statistic"])
            pitch.heatmap(stats, ax=ax, cmap="inferno", edgecolors=style.PANEL, alpha=0.9)
        else:
            fig, ax = self._map_axes(False, xy, figsize=(11, 7.5))
            ax.hexbin(xy[:, 0], xy[:, 1], gridsize=28, cmap="inferno", mincnt=1, alpha=0.95)
        ax.set_title(title, color=style.TEXT)
        return self._save(fig, filename)

    # ------------------------------------------------------------------ team mode

    def team_charts(self, report: MatchReport) -> dict[str, Path]:
        team = report.focus_team
        builders = {
            "Possession": lambda: self.possession(report),
            "Distance by player": lambda: self.team_distance(team),
            "Top speed by player": lambda: self.team_top_speed(team),
            "Team heatmap": lambda: self.heatmap(team.players, report.pitch_coordinates, f"Team {team.color_name} - heatmap", "team_heatmap.png"),
            "Average positions": lambda: self.average_positions(team, report.pitch_coordinates),
            "Team events": lambda: self.team_events(team),
            "Event timeline": lambda: self.event_timeline(team.events, f"Team {team.color_name} - match events", "team_event_timeline.png"),
        }
        return self._run(builders)

    def possession(self, report: MatchReport) -> Path | None:
        share = report.possession.team_share()
        if not share:
            return None
        frames = sorted(report.possession.team_by_frame)
        team_id = report.focus_team.team_id
        team_hex = bgr_to_hex(ensure_visible(report.focus_team.color_bgr))
        path = report.ball_path
        fig, (ax_pie, ax_line) = plt.subplots(
            1, 2, figsize=(11, 5.2) if path else (14, 4.5), gridspec_kw={"width_ratios": [1, 2.6 if path else 2.4]}
        )
        ax_pie.grid(False)
        ours = share.get(team_id, 0.0)
        ax_pie.pie([ours, 1 - ours], colors=[team_hex, style.GRID], startangle=90, counterclock=False,
                   wedgeprops={"width": 0.35, "edgecolor": style.BACKGROUND})
        ax_pie.text(0, 0, f"{ours * 100:.0f}%", ha="center", va="center", fontsize=22, fontweight="bold")
        ax_pie.set_title(f"{report.focus_team.color_name} vs {report.opponent_color}")

        if path is not None:
            self._draw_ball_path(ax_line, path, report)
            return self._save(fig, "team_possession.png")

        window = max(int(30 * report.video.effective_fps), 5)
        rolling = report.possession.rolling_team_share(frames, team_id, window)
        seconds = np.array(frames) / report.video.fps
        ax_line.fill_between(seconds, 0.5, rolling, where=rolling >= 0.5, color=team_hex, alpha=0.7, interpolate=True)
        ax_line.fill_between(seconds, 0.5, rolling, where=rolling < 0.5, color=style.MUTED, alpha=0.5, interpolate=True)
        ax_line.axhline(0.5, color=style.TEXT, linewidth=0.8)
        ax_line.set_ylim(0, 1)
        ax_line.set_ylabel("Possession share (30 s rolling)")
        ax_line.set_xlabel("Video time (s)")
        ax_line.set_title("Possession momentum")
        return self._save(fig, "team_possession.png")

    def _draw_ball_path(self, ax, path, report: MatchReport) -> None:
        """The ball's route over the pitch; each stretch is coloured by the team controlling it."""
        Pitch(pitch_type="custom", pitch_length=self.pitch_length, pitch_width=self.pitch_width,
              pitch_color="#1F5130", line_color="#DDDDDD", stripe=True, stripe_color="#22593A").draw(ax=ax)
        colors = {team: bgr_to_hex(ensure_visible(c)) for team, c in path.team_colors_bgr.items()}
        loose = "#8A94A3"
        max_gap = int(path.fps)  # a gap over ~1 s means the ball was lost or the camera cut: draw no line across it
        segments, line_colors, widths = [], [], []
        for i in range(len(path.frames) - 1):
            a, b = path.xy_m[i], path.xy_m[i + 1]
            if path.frames[i + 1] - path.frames[i] > max_gap or float(np.hypot(*(b - a))) > 35:
                continue
            team = path.team_at_point[i]
            segments.append([a, b])
            line_colors.append(colors.get(team, loose))
            widths.append(2.6 if team in colors else 1.2)
        ax.add_collection(LineCollection(segments, colors=line_colors, linewidths=widths, zorder=3))
        ax.scatter(*path.xy_m[0], s=70, color="#FFFFFF", edgecolor="#111111", zorder=5)
        ax.scatter(*path.xy_m[-1], s=70, marker="s", color="#FFFFFF", edgecolor="#111111", zorder=5)
        ax.annotate("start", path.xy_m[0], xytext=(6, 6), textcoords="offset points", color="#FFFFFF", fontsize=9, zorder=6)
        ax.annotate("end", path.xy_m[-1], xytext=(6, 6), textcoords="offset points", color="#FFFFFF", fontsize=9, zorder=6)

        focus_id = report.focus_team.team_id
        names = {focus_id: report.focus_team.color_name}
        names.update({team: report.opponent_color for team in colors if team != focus_id})
        handles = [Line2D([0], [0], color=colors[t], lw=3, label=f"{names[t]} in possession") for t in colors]
        handles.append(Line2D([0], [0], color=loose, lw=1.5, label="Loose ball"))
        ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False, fontsize=9)
        ax.set_title("Ball movement - colour shows who has the ball")

    @staticmethod
    def _team_chart_height(team: TeamReport) -> float:
        """One height for the per-player team charts, so the pair shown side by side lines up."""
        n = min(sum(p.metrics.kinematics.total_distance_m > 0 for p in team.players), 16)
        return max(0.45 * n + 1.8, _ROW_FIGSIZE[1])

    def team_distance(self, team: TeamReport) -> Path | None:
        players = [p for p in team.players if p.metrics.kinematics.total_distance_m > 0][:16]
        if not players:
            return None
        fig, ax = plt.subplots(figsize=(11, self._team_chart_height(team)))
        labels = [f"Player {p.player_id}" for p in players]
        left = np.zeros(len(players))
        for zone in self.zones_kmh:
            values = np.array([p.metrics.kinematics.distance_by_zone_m.get(zone, 0.0) for p in players])
            ax.barh(labels, values, left=left, color=style.ZONE_COLORS.get(zone, style.ACCENT), label=_ZONE_LABELS.get(zone, zone))
            left += values
        ax.invert_yaxis()
        ax.set_xlabel("Distance on screen (m)")
        ax.legend(ncol=5, loc="lower right", fontsize=8)
        ax.set_title("Distance covered by intensity zone")
        return self._save(fig, "team_distance.png")

    def team_top_speed(self, team: TeamReport) -> Path | None:
        players = sorted([p for p in team.players if p.metrics.kinematics.top_speed_kmh > 0],
                         key=lambda p: -p.metrics.kinematics.top_speed_kmh)[:16]
        if not players:
            return None
        fig, ax = plt.subplots(figsize=(11, self._team_chart_height(team)))
        speeds = [p.metrics.kinematics.top_speed_kmh for p in players]
        bars = ax.bar([str(p.player_id) for p in players], speeds, color=[style.FAILURE if s >= 25 else style.ACCENT for s in speeds])
        for bar, speed, p in zip(bars, speeds, players):
            ax.text(bar.get_x() + bar.get_width() / 2, speed + 0.4, f"{speed:.1f}\n{len(p.metrics.kinematics.sprints)} spr",
                    ha="center", fontsize=8, color=style.TEXT)
        ax.axhline(25, color=style.FAILURE, linestyle="--", linewidth=1, label="Sprint threshold 25 km/h")
        ax.set_xlabel("Player id")
        ax.set_ylabel("Top speed (km/h)")
        ax.set_ylim(0, max(speeds) + 6)
        ax.legend()
        ax.set_title("Top speed and sprint count")
        return self._save(fig, "team_top_speed.png")

    def average_positions(self, team: TeamReport, on_pitch: bool) -> Path | None:
        players = [p for p in team.players if len(p.metrics.series) >= 10]
        if len(players) < 2:
            return None
        centers = np.stack([np.median(p.metrics.series.xy_m, axis=0) for p in players])
        sizes = np.array([p.metrics.on_screen_s for p in players])
        fig, ax = self._map_axes(on_pitch, centers, figsize=(11, 7.5))
        team_hex = bgr_to_hex(ensure_visible(team.color_bgr))
        ax.scatter(centers[:, 0], centers[:, 1], s=200 + 1200 * sizes / sizes.max(), color=team_hex, edgecolors="white", linewidths=1.5, zorder=4)
        for p, (x, y) in zip(players, centers):
            ax.text(x, y, str(p.player_id), ha="center", va="center", fontsize=9, fontweight="bold", color="black", zorder=5)
        width = np.ptp(centers[:, 1]) if on_pitch else np.ptp(centers[:, 0])
        depth = np.ptp(centers[:, 0]) if on_pitch else np.ptp(centers[:, 1])
        ax.set_title(f"Average positions (bubble = time on screen)  -  width {width:.0f} m, depth {depth:.0f} m", color=style.TEXT)
        return self._save(fig, "team_average_positions.png")

    def team_events(self, team: TeamReport) -> Path | None:
        if not team.events:
            return None
        totals = Counter(e.event_type.value for e in team.events)
        wins = Counter(e.event_type.value for e in team.events if e.successful)
        names = [n for n, _ in totals.most_common()]
        fig, ax = plt.subplots(figsize=_ROW_FIGSIZE)
        x = np.arange(len(names))
        ax.bar(x, [wins[n] for n in names], width=0.6, color=style.SUCCESS, label="Successful")
        ax.bar(x, [totals[n] - wins[n] for n in names], width=0.6, bottom=[wins[n] for n in names], color=style.FAILURE, label="Unsuccessful")
        half = max(len(names), 4) / 2  # a clip with one event type must not turn into one full-width bar
        ax.set_xlim((len(names) - 1) / 2 - half, (len(names) - 1) / 2 + half)
        ax.set_ylim(0, max(totals.values()) * 1.15)
        ax.set_xticks(x, [n.replace("_", "\n") for n in names], fontsize=9)
        ax.set_ylabel("Count")
        ax.legend()
        ax.set_title(f"Team {team.color_name} - event totals (AI events)")
        return self._save(fig, "team_events.png")

    # ------------------------------------------------------------------ helpers

    def _map_axes(self, on_pitch: bool, xy: np.ndarray, figsize):
        if on_pitch:
            pitch = Pitch(pitch_type="custom", pitch_length=self.pitch_length, pitch_width=self.pitch_width,
                          pitch_color="#1F5130", line_color="#DDDDDD", stripe=True, stripe_color="#22593A")
            return pitch.draw(figsize=figsize)
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_facecolor("#1F5130")
        ax.grid(color="#2F6B42", linewidth=0.6)
        pad = 3.0
        ax.set_xlim(xy[:, 0].min() - pad, xy[:, 0].max() + pad)
        ax.set_ylim(xy[:, 1].max() + pad, xy[:, 1].min() - pad)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("metres (camera-relative)")
        ax.set_ylabel("metres (camera-relative)")
        return fig, ax

    def _run(self, builders) -> dict[str, Path]:
        charts = {}
        for name, build in builders.items():
            path = build()
            if path is not None:
                charts[name] = path
        return charts

    def _save(self, fig, filename: str) -> Path:
        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path


def _gaussian_blur(grid: np.ndarray) -> np.ndarray:
    return gaussian_filter(grid, sigma=1.0)
