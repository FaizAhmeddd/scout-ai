"""Football player & team analysis — single entry point.

Usage:
    uv run python main.py                                   # fully interactive
    uv run python main.py --video match.mp4                 # asks for team / player
    uv run python main.py --video match.mp4 --team 1 --player 3 --jersey 10 --name "Saka"
    uv run python main.py --video match.mp4 --team 2 --player all
"""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from app.core.app_config import load_app_config
from app.core.config import settings
from app.engine.interactive.target_selector import InteractiveTargetSelector, PresetTargetSelector, open_file
from app.engine.pipeline.match_analysis_pipeline import AnalysisOutputs, MatchAnalysisPipeline
from app.engine.reports.html_report import ai_status

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pose-based football analysis with agentic AI video understanding")
    parser.add_argument("--video", type=Path, help="Path to the match video")
    parser.add_argument("--team", type=int, help="Team number from the contact sheet (1 or 2). Omit to choose interactively")
    parser.add_argument("--player", help="Player number from the contact sheet, or 'all' for the whole team")
    parser.add_argument("--jersey", type=int, help="Jersey number of the selected player (helps the AI)")
    parser.add_argument("--name", default="", help="Display name of the selected player")
    parser.add_argument("--config", type=Path, help="Alternative config.yaml")
    parser.add_argument("--no-gemini", action="store_true", help="Skip AI event analysis")
    parser.add_argument("--no-video", action="store_true", help="Skip rendering the annotated video")
    parser.add_argument("--no-open", action="store_true", help="Do not open contact sheets or the report automatically")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def build_selector(args: argparse.Namespace):
    if args.team is None:
        return InteractiveTargetSelector(console, open_images=not args.no_open)
    player = None if args.player in (None, "all") else int(args.player)
    return PresetTargetSelector(args.team, player, args.jersey, args.name)


def resolve_video(args: argparse.Namespace) -> Path:
    path = args.video or Path(Prompt.ask("Path to the match video").strip().strip('"'))
    if not path.exists():
        console.print(f"[red]Video not found:[/red] {path}")
        sys.exit(1)
    return path


def print_summary(outputs: AnalysisOutputs) -> None:
    report = outputs.report
    table = Table(title="Results", show_header=False, title_style="bold yellow")
    if report.focus_player:
        p = report.focus_player
        kin = p.metrics.kinematics
        table.add_row("Player", f"{p.label}  (OVR {p.ratings.overall}, {p.ratings.position})")
        table.add_row("Attributes", "  ".join(f"{k} {v}" for k, v in p.ratings.attributes.items()))
        table.add_row("Distance", f"{kin.total_distance_m:.0f} m  ({kin.distance_per_min:.0f} m/min)")
        table.add_row("Top speed / sprints", f"{kin.top_speed_kmh:.1f} km/h / {len(kin.sprints)}")
        if p.counts:
            c = p.counts
            table.add_row("Passes", f"{c.passes_completed}/{c.passes_attempted}")
            table.add_row("Dribbles", f"{c.dribbles_successful}/{c.dribbles_attempted}")
            table.add_row("Shots (on target)", f"{c.shots} ({c.shots_on_target})")
            table.add_row("Defensive actions", str(c.defensive_actions))
    else:
        team = report.focus_team
        table.add_row("Team", f"{team.color_name} kit, {len(team.players)} players tracked")
        table.add_row("Possession", f"{(team.possession_share or 0) * 100:.0f}%")
        if team.counts:
            table.add_row("Passes", f"{team.counts.passes_completed}/{team.counts.passes_attempted}")
            table.add_row("Shots", f"{team.counts.shots} ({team.counts.shots_on_target} on target)")
    table.add_row("AI events", ai_status(report.gemini_status))
    console.print(table)

    lines = [f"[bold]Report:[/bold]   {outputs.report_html}"]
    if outputs.annotated_video:
        lines.append(f"[bold]Video:[/bold]    {outputs.annotated_video}")
    lines.append(f"[bold]Graphs:[/bold]   {outputs.output_dir / 'charts'}  ({len(outputs.charts) + bool(outputs.player_card)} files)")
    lines.append(f"[bold]Data:[/bold]     {outputs.metrics_json}")
    console.print(Panel("\n".join(lines), title="Outputs", border_style="green"))


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )
    for noisy in ("httpx", "google_genai", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    console.print(Panel.fit("[bold yellow]SCOUTAI[/bold yellow]\nPose tracking  |  Agentic video AI  |  FC-style ratings"))
    config = load_app_config(args.config)
    video = resolve_video(args)

    pipeline = MatchAnalysisPipeline(config, settings.GEMINI_API_KEY, console)
    outputs = pipeline.run(video, build_selector(args), use_gemini=not args.no_gemini, render_video=not args.no_video)

    print_summary(outputs)
    if config.report.open_when_done and not args.no_open:
        open_file(outputs.report_html)


if __name__ == "__main__":
    main()
