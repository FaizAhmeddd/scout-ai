from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Rectangle

from app.engine.fusion.rating_model import ATTRIBUTES
from app.engine.fusion.report_builder import PlayerReport
from app.engine.render.palette import BGR, bgr_to_hex, ensure_visible
from app.engine.reports import style

# (top, bottom, text) gradients per card tier, like the in-game rarity colours.
_TIERS = {
    "elite": ("#1B1B1B", "#3A2E05", "#F5D76E"),
    "gold": ("#F9E39A", "#B8862F", "#2B2105"),
    "silver": ("#F1F3F5", "#9AA3AD", "#1E242B"),
    "bronze": ("#E8B48A", "#8A5530", "#2A1708"),
}


# Card layout (axes units: x 0-1, y 0-1.4).
_BADGE_X = 0.2
_PHOTO_X = 0.61
_PHOTO_MAX_W = 0.5
_PHOTO_TOP, _PHOTO_BOTTOM = 1.3, 0.72
_STAT_GUTTERS = (0.265, 0.705)  # value | label split for the left and right attribute columns


class PlayerCardRenderer:
    """Renders an FC/FIFA Ultimate-Team style card from the computed ratings."""

    def __init__(self, dpi: int):
        self.dpi = dpi

    def render(self, player: PlayerReport, team_color: BGR, path: Path) -> Path:
        style.apply_theme()
        ratings = player.ratings
        top, bottom, ink = _TIERS[self._tier(ratings.overall)]

        fig = plt.figure(figsize=(4.4, 6.2))
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.4)
        ax.axis("off")

        card = FancyBboxPatch((0.04, 0.03), 0.92, 1.34, boxstyle="round,pad=0,rounding_size=0.08",
                              linewidth=3, edgecolor=ink, facecolor="none", zorder=3)
        ax.add_patch(card)
        gradient = np.linspace(0, 1, 256).reshape(-1, 1)
        image = ax.imshow(gradient, extent=(0.04, 0.96, 0.03, 1.37), aspect="auto", zorder=1,
                          cmap=_two_color_cmap(bottom, top), origin="lower")
        image.set_clip_path(card)

        # Header: rating / position / kit swatch stacked in a left column, photo centred in the space to its right.
        ax.text(_BADGE_X, 1.215, str(ratings.overall), fontsize=44, fontweight="bold", color=ink, ha="center", va="center", zorder=4)
        ax.text(_BADGE_X, 1.095, ratings.position, fontsize=16, fontweight="bold", color=ink, ha="center", va="center", zorder=4)
        ax.plot([_BADGE_X - 0.07, _BADGE_X + 0.07], [1.035, 1.035], color=ink, linewidth=1, alpha=0.5, zorder=4)
        ax.add_patch(Rectangle((_BADGE_X - 0.055, 0.955), 0.11, 0.05, color=bgr_to_hex(ensure_visible(team_color)),
                               zorder=4, ec=ink, lw=1))

        if player.metrics.player.thumbnail is not None:
            rgb = cv2.cvtColor(player.metrics.player.thumbnail, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            box_h = _PHOTO_TOP - _PHOTO_BOTTOM
            box_w = min(box_h * w / h, _PHOTO_MAX_W)
            box_h = min(box_h, box_w * h / w)
            cy = (_PHOTO_TOP + _PHOTO_BOTTOM) / 2
            extent = (_PHOTO_X - box_w / 2, _PHOTO_X + box_w / 2, cy - box_h / 2, cy + box_h / 2)
            ax.imshow(rgb, extent=extent, zorder=4, aspect="auto")
            ax.add_patch(Rectangle((extent[0], extent[2]), box_w, box_h, fill=False, ec=ink, lw=1, alpha=0.4, zorder=5))

        # Name band, centred on the card.
        ax.plot([0.12, 0.88], [0.665, 0.665], color=ink, linewidth=1.2, alpha=0.6, zorder=4)
        name = player.label.upper()
        name = name if len(name) <= 22 else name[:21] + "…"
        ax.text(0.5, 0.605, name, fontsize=19 if len(name) <= 16 else 15, fontweight="bold", color=ink,
                ha="center", va="center", zorder=4)
        ax.plot([0.12, 0.88], [0.545, 0.545], color=ink, linewidth=1.2, alpha=0.6, zorder=4)

        # Attributes: two columns mirrored around the centre divider; value right-aligned, label left-aligned
        # against a shared gutter so every row lines up.
        for i, attr in enumerate(ATTRIBUTES):
            column, row = divmod(i, 3)
            gutter = _STAT_GUTTERS[column]
            y = 0.455 - row * 0.105
            marker = "*" if attr in ratings.estimated else ""
            ax.text(gutter - 0.015, y, f"{ratings.attributes[attr]}", fontsize=20, fontweight="bold", color=ink,
                    ha="right", va="center", zorder=4)
            ax.text(gutter + 0.025, y, f"{attr}{marker}", fontsize=14, color=ink, ha="left", va="center", zorder=4)
        ax.plot([0.5, 0.5], [0.2, 0.5], color=ink, linewidth=1, alpha=0.5, zorder=4)

        ax.text(0.5, 0.125, "SCOUTAI", fontsize=8, fontweight="bold", color=ink, ha="center", va="center", alpha=0.85, zorder=4)
        if ratings.estimated:
            ax.text(0.5, 0.08, "* limited evidence in this clip", fontsize=6.5, color=ink, ha="center", va="center",
                    alpha=0.7, zorder=4)

        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=self.dpi, transparent=True)
        plt.close(fig)
        return path

    @staticmethod
    def _tier(overall: int) -> str:
        if overall >= 85:
            return "elite"
        if overall >= 75:
            return "gold"
        if overall >= 65:
            return "silver"
        return "bronze"


def _two_color_cmap(low: str, high: str) -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("card", [low, high])
