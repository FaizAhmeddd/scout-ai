import base64
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.engine.fusion.report_builder import MatchReport, PlayerReport
from app.engine.render.palette import bgr_to_hex, ensure_visible

_TEMPLATES = Path(__file__).parent / "templates"


class HtmlReportWriter:
    """Self-contained HTML report: charts and card are embedded, the annotated video sits next to it."""

    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=select_autoescape(["html", "j2"]))

    def write(
        self,
        report: MatchReport,
        charts: dict[str, Path],
        card_path: Path | None,
        video_path: Path | None,
        output_path: Path,
    ) -> Path:
        template = self.env.get_template("report.html.j2")
        focus = report.focus_player
        html = template.render(
            report=report,
            generated=datetime.now().strftime("%d %b %Y %H:%M"),
            mode="Player analysis" if focus else "Team analysis",
            team_hex=bgr_to_hex(ensure_visible(report.focus_team.color_bgr)),
            card=_b64(card_path) if card_path else None,
            video=video_path.name if video_path else None,
            charts=[(name, _b64(path)) for name, path in charts.items()],
            tiles=self._player_tiles(focus) if focus else self._team_tiles(report),
            physical_rows=self._physical_rows(focus) if focus else [],
            event_rows=self._event_rows(focus.counts) if focus and focus.counts else (
                self._event_rows(report.focus_team.counts) if report.focus_team.counts else []
            ),
            team_rows=self._team_rows(report) if not focus else [],
            assessment=focus.assessment if focus else None,
            ratings=focus.ratings if focus else None,
            ai_status=ai_status(report.gemini_status),
        )
        output_path.write_text(html, encoding="utf-8")
        return output_path

    @staticmethod
    def _player_tiles(p: PlayerReport) -> list[tuple[str, str, str]]:
        kin, c = p.metrics.kinematics, p.counts
        tiles = [
            ("Distance", f"{kin.total_distance_m:.0f} m", f"{kin.distance_per_min:.0f} m/min"),
            ("Top speed", f"{kin.top_speed_kmh:.1f}", "km/h"),
            ("Sprints", str(len(kin.sprints)), f"{kin.high_intensity_distance_m:.0f} m high-intensity"),
            ("Ball control", f"{p.possession_s:.1f} s", f"{p.touches} possessions"),
        ]
        if c is not None:
            accuracy = f"{c.pass_accuracy * 100:.0f}% accuracy" if c.pass_accuracy is not None else "no passes"
            tiles += [
                ("Passes", f"{c.passes_completed}/{c.passes_attempted}", accuracy),
                ("Dribbles", f"{c.dribbles_successful}/{c.dribbles_attempted}", "successful / attempted"),
                ("Shots", f"{c.shots_on_target}/{c.shots}", f"{c.goals} goals"),
                ("Defensive actions", str(c.defensive_actions), f"{c.duels_won}/{c.duels} duels won"),
            ]
        return tiles

    @staticmethod
    def _team_tiles(report: MatchReport) -> list[tuple[str, str, str]]:
        team = report.focus_team
        distance = sum(p.metrics.kinematics.total_distance_m for p in team.players)
        fastest = max(team.players, key=lambda p: p.metrics.kinematics.top_speed_kmh, default=None)
        tiles = [
            ("Possession", f"{(team.possession_share or 0) * 100:.0f}%", f"vs {report.opponent_color}"),
            ("Team distance", f"{distance / 1000:.2f} km", "on screen"),
            ("Players tracked", str(len(team.players)), "identities after stitching"),
            ("Fastest", f"{fastest.metrics.kinematics.top_speed_kmh:.1f} km/h" if fastest else "--",
             f"player {fastest.player_id}" if fastest else ""),
        ]
        if team.counts is not None:
            c = team.counts
            tiles += [
                ("Passes", f"{c.passes_completed}/{c.passes_attempted}",
                 f"{c.pass_accuracy * 100:.0f}% accuracy" if c.pass_accuracy is not None else ""),
                ("Shots", f"{c.shots_on_target}/{c.shots}", f"{c.goals} goals"),
                ("Dribbles", f"{c.dribbles_successful}/{c.dribbles_attempted}", "successful / attempted"),
                ("Defensive actions", str(c.defensive_actions), f"{c.duels_won}/{c.duels} duels won"),
            ]
        return tiles

    @staticmethod
    def _physical_rows(p: PlayerReport) -> list[tuple[str, str]]:
        kin, pose = p.metrics.kinematics, p.metrics.pose
        rows = [
            ("Time on screen", f"{p.metrics.on_screen_s:.0f} s"),
            ("Total distance", f"{kin.total_distance_m:.0f} m"),
            ("Average speed (moving)", f"{kin.avg_speed_kmh:.1f} km/h"),
            ("Top speed", f"{kin.top_speed_kmh:.1f} km/h"),
        ]
        rows += [(f"Distance - {zone.replace('_', ' ')}", f"{d:.0f} m") for zone, d in kin.distance_by_zone_m.items()]
        rows += [
            ("Sprints (>25 km/h, >1 s)", str(len(kin.sprints))),
            ("Accelerations / decelerations (>3 m/s2)", f"{kin.accelerations} / {kin.decelerations}"),
            ("Running cadence", f"{pose.cadence_spm:.0f} steps/min" if pose.cadence_spm else "n/a"),
            ("Trunk lean while running", f"{pose.trunk_lean_deg:.0f} deg" if pose.trunk_lean_deg is not None else "n/a"),
            ("Pose keypoint visibility", f"{pose.keypoint_visibility * 100:.0f}%"),
            ("Tracker fragments merged", str(len(p.metrics.player.source_track_ids))),
        ]
        return rows

    @staticmethod
    def _event_rows(c) -> list[tuple[str, str]]:
        def pct(a: int, b: int) -> str:
            return f"{a}/{b} ({a / b * 100:.0f}%)" if b else "0"

        return [
            ("Passes completed", pct(c.passes_completed, c.passes_attempted)),
            ("Short / long passes", f"{c.short_passes} / {c.long_passes} ({c.long_passes_completed} long completed)"),
            ("Progressive passes", str(c.progressive_passes)),
            ("Key passes", str(c.key_passes)),
            ("Assists", str(c.assists)),
            ("Crosses completed", pct(c.crosses_completed, c.crosses_attempted)),
            ("Shots on target", pct(c.shots_on_target, c.shots)),
            ("Goals", str(c.goals)),
            ("Dribbles successful", pct(c.dribbles_successful, c.dribbles_attempted)),
            ("Tackles won", pct(c.tackles_won, c.tackles_attempted)),
            ("Interceptions", str(c.interceptions)),
            ("Clearances / blocks", f"{c.clearances} / {c.blocks}"),
            ("Ball recoveries", str(c.ball_recoveries)),
            ("Aerial duels won", pct(c.aerial_duels_won, c.aerial_duels)),
            ("Ground duels won", pct(c.ground_duels_won, c.ground_duels)),
            ("Possession lost", str(c.possession_lost)),
            ("Fouls committed / won", f"{c.fouls_committed} / {c.fouls_won}"),
            ("Cards (Y/R)", f"{c.yellow_cards} / {c.red_cards}"),
        ]

    @staticmethod
    def _team_rows(report: MatchReport) -> list[list[str]]:
        rows = []
        for p in report.focus_team.players:
            kin = p.metrics.kinematics
            rows.append([
                str(p.player_id),
                f"{p.metrics.on_screen_s:.0f}",
                f"{kin.total_distance_m:.0f}",
                f"{kin.top_speed_kmh:.1f}",
                str(len(kin.sprints)),
                f"{kin.high_intensity_distance_m:.0f}",
                f"{p.possession_s:.1f}",
                str(p.ratings.attributes["PAC"]),
                str(p.ratings.attributes["PHY"]),
            ])
        return rows


def ai_status(status: str) -> str:
    """User-facing AI analysis status without provider or model details."""
    if status.startswith("ok"):
        return "complete"
    return {"disabled": "off", "no API key": "not configured"}.get(status, "unavailable")


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")
