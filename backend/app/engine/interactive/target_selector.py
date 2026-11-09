import os
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.prompt import IntPrompt, Prompt

from app.engine.domain.models import OTHER_TEAM, AnalysisTarget, PlayerTrack, TeamAssignment
from app.engine.interactive.contact_sheet import ContactSheetBuilder

_MIN_ON_SCREEN_S = 2.0
_MAX_CANDIDATES = 40


@dataclass
class SelectionContext:
    players: list[PlayerTrack]
    teams: TeamAssignment
    frame_seconds: float
    workdir: Path

    def team_players(self, team_id: int) -> list[PlayerTrack]:
        """Selectable players of a team, longest on screen first (stable order across runs)."""
        candidates = [
            p for p in self.players
            if p.team_id == team_id and p.thumbnail is not None
            and len(p.observations) * self.frame_seconds >= _MIN_ON_SCREEN_S
        ]
        candidates.sort(key=lambda p: (-len(p.observations), p.player_id))
        return candidates[:_MAX_CANDIDATES]

    def on_screen_s(self, player: PlayerTrack) -> float:
        return len(player.observations) * self.frame_seconds

    def team_ids(self) -> list[int]:
        return sorted(t for t in self.teams.color_names if t != OTHER_TEAM)


class TargetSelector(ABC):
    @abstractmethod
    def select(self, context: SelectionContext) -> AnalysisTarget: ...


class PresetTargetSelector(TargetSelector):
    """Non-interactive selection from CLI flags / API parameters. Numbers match the contact sheets (1-based)."""

    def __init__(self, team_number: int, player_number: int | None, jersey_number: int | None = None, name: str = ""):
        self.team_number = team_number
        self.player_number = player_number
        self.jersey_number = jersey_number
        self.name = name

    def select(self, context: SelectionContext) -> AnalysisTarget:
        team_ids = context.team_ids()
        if not 1 <= self.team_number <= len(team_ids):
            raise ValueError(f"Team must be between 1 and {len(team_ids)}")
        team_id = team_ids[self.team_number - 1]
        if self.player_number is None:
            return AnalysisTarget(team_id=team_id, label=f"Team {self.team_number} ({context.teams.color_names[team_id]})")

        candidates = context.team_players(team_id)
        if not 1 <= self.player_number <= len(candidates):
            raise ValueError(f"Player must be between 1 and {len(candidates)} for team {self.team_number}")
        player = candidates[self.player_number - 1]
        return AnalysisTarget(
            team_id=team_id,
            player_id=player.player_id,
            jersey_number=self.jersey_number,
            label=self.name or _default_label(self.jersey_number, self.player_number),
        )


class InteractiveTargetSelector(TargetSelector):
    """Asks which team, then whole team or one player, showing contact sheets of the tracked players."""

    def __init__(self, console: Console | None = None, open_images: bool = True):
        self.console = console or Console()
        self.open_images = open_images
        self.sheets = ContactSheetBuilder()

    def select(self, context: SelectionContext) -> AnalysisTarget:
        team_ids = context.team_ids()
        rows = [
            (f"TEAM {n}  -  {context.teams.color_names[t].upper()} KIT", context.teams.colors_bgr[t], context.team_players(t))
            for n, t in enumerate(team_ids, start=1)
        ]
        team_sheet = self.sheets.team_sheet(rows, context.workdir / "selection" / "teams.png")
        self._show(team_sheet)

        self.console.rule("[bold]Choose a team")
        for n, t in enumerate(team_ids, start=1):
            self.console.print(f"  [bold]{n}[/bold]  {context.teams.color_names[t]} kit  ({len(context.team_players(t))} players tracked)")
        team_number = IntPrompt.ask("Which team do you want to analyse?", choices=[str(n) for n in range(1, len(team_ids) + 1)])
        team_id = team_ids[team_number - 1]

        candidates = context.team_players(team_id)
        player_sheet = self.sheets.player_sheet(
            f"TEAM {team_number} PLAYERS  -  pick a number",
            context.teams.colors_bgr[team_id],
            candidates,
            [context.on_screen_s(p) for p in candidates],
            context.workdir / "selection" / f"team{team_number}_players.png",
        )
        self._show(player_sheet)

        self.console.rule("[bold]Whole team or a single player?")
        choice = Prompt.ask(
            f"Enter a player number [1-{len(candidates)}] from the sheet, or 'all' for the whole team",
            default="all",
        ).strip().lower()
        if choice == "all":
            return AnalysisTarget(team_id=team_id, label=f"Team {team_number} ({context.teams.color_names[team_id]})")

        if not choice.isdigit() or not 1 <= int(choice) <= len(candidates):
            self.console.print("[red]Invalid choice; analysing the whole team instead.[/red]")
            return AnalysisTarget(team_id=team_id, label=f"Team {team_number} ({context.teams.color_names[team_id]})")

        player_number = int(choice)
        jersey_raw = Prompt.ask("Jersey number if you know it (helps the AI find the player)", default="").strip()
        jersey = int(jersey_raw) if jersey_raw.isdigit() else None
        name = Prompt.ask("Player name for the report (optional)", default="").strip()
        player = candidates[player_number - 1]
        return AnalysisTarget(
            team_id=team_id,
            player_id=player.player_id,
            jersey_number=jersey,
            label=name or _default_label(jersey, player_number),
        )

    def _show(self, path: Path) -> None:
        self.console.print(f"[cyan]Contact sheet:[/cyan] {path}")
        if self.open_images:
            open_file(path)


def open_file(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def _default_label(jersey: int | None, player_number: int) -> str:
    return f"#{jersey}" if jersey is not None else f"Player {player_number}"
