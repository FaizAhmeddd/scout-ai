from pathlib import Path

import cv2
import numpy as np

from app.engine.domain.models import PlayerTrack
from app.engine.render.palette import BGR, readable_text_color

_TILE_W, _TILE_H = 120, 200
_LABEL_H = 34
_COLUMNS = 8
_BACKGROUND = (28, 28, 28)
_FONT = cv2.FONT_HERSHEY_SIMPLEX


class ContactSheetBuilder:
    """Renders thumbnail grids so the user can recognise teams and players before choosing."""

    def team_sheet(self, rows: list[tuple[str, BGR, list[PlayerTrack]]], path: Path) -> Path:
        blocks = []
        for title, color, players in rows:
            header = self._header(title, color, _COLUMNS * _TILE_W)
            tiles = [self._tile(p.thumbnail, "", color) for p in players[:_COLUMNS]]
            blocks.extend([header, self._grid(tiles)])
        return self._save(np.vstack(blocks), path)

    def player_sheet(self, title: str, color: BGR, players: list[PlayerTrack], seconds_on_screen: list[float], path: Path) -> Path:
        header = self._header(title, color, _COLUMNS * _TILE_W)
        tiles = [
            self._tile(p.thumbnail, f"[{i}] {secs:.0f}s", color)
            for i, (p, secs) in enumerate(zip(players, seconds_on_screen), start=1)
        ]
        return self._save(np.vstack([header, self._grid(tiles)]), path)

    @staticmethod
    def _header(text: str, color: BGR, width: int) -> np.ndarray:
        header = np.full((48, width, 3), color, dtype=np.uint8)
        cv2.putText(header, text, (12, 33), _FONT, 0.85, readable_text_color(color), 2, cv2.LINE_AA)
        return header

    @staticmethod
    def _tile(thumbnail: np.ndarray | None, label: str, color: BGR) -> np.ndarray:
        tile = np.full((_TILE_H + _LABEL_H, _TILE_W, 3), _BACKGROUND, dtype=np.uint8)
        if thumbnail is not None and thumbnail.size:
            h, w = thumbnail.shape[:2]
            scale = min(_TILE_W / w, _TILE_H / h)
            resized = cv2.resize(thumbnail, (max(int(w * scale), 1), max(int(h * scale), 1)))
            y0 = (_TILE_H - resized.shape[0]) // 2
            x0 = (_TILE_W - resized.shape[1]) // 2
            tile[y0: y0 + resized.shape[0], x0: x0 + resized.shape[1]] = resized
        cv2.rectangle(tile, (0, 0), (_TILE_W - 1, _TILE_H + _LABEL_H - 1), color, 2)
        if label:
            cv2.putText(tile, label, (6, _TILE_H + 24), _FONT, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return tile

    @staticmethod
    def _grid(tiles: list[np.ndarray]) -> np.ndarray:
        if not tiles:
            return np.full((_TILE_H + _LABEL_H, _COLUMNS * _TILE_W, 3), _BACKGROUND, dtype=np.uint8)
        blank = np.full_like(tiles[0], _BACKGROUND)
        rows = []
        for start in range(0, len(tiles), _COLUMNS):
            row = tiles[start: start + _COLUMNS]
            row += [blank] * (_COLUMNS - len(row))
            rows.append(np.hstack(row))
        return np.vstack(rows)

    @staticmethod
    def _save(image: np.ndarray, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)
        return path
