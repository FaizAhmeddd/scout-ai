import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

BACKGROUND = "#0E1117"
PANEL = "#161B22"
GRID = "#2A313C"
TEXT = "#E6EDF3"
MUTED = "#8B949E"
ACCENT = "#FFE600"
SUCCESS = "#2EA043"
FAILURE = "#F85149"
ZONE_COLORS = {
    "walking": "#3B82F6",
    "jogging": "#22C55E",
    "running": "#EAB308",
    "high_speed": "#F97316",
    "sprinting": "#EF4444",
}


def apply_theme() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": PANEL,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": TEXT,
            "legend.facecolor": PANEL,
            "legend.edgecolor": GRID,
            "font.family": "DejaVu Sans",
            "savefig.facecolor": BACKGROUND,
        }
    )


def title_text(fig, title: str, subtitle: str = "") -> None:
    fig.text(0.02, 0.97, title, fontsize=16, fontweight="bold", color=TEXT, va="top")
    if subtitle:
        fig.text(0.02, 0.915, subtitle, fontsize=10, color=MUTED, va="top")
