import colorsys

import cv2
import numpy as np

BGR = tuple[int, int, int]

FOCUS_COLOR: BGR = (0, 255, 255)  # neon yellow
BALL_COLOR: BGR = (0, 200, 255)
OTHER_COLOR: BGR = (170, 170, 170)
TEXT_COLOR: BGR = (255, 255, 255)
PANEL_COLOR: BGR = (20, 20, 20)

EVENT_COLORS_HEX: dict[str, str] = {
    "pass": "#4FC3F7",
    "cross": "#29B6F6",
    "shot": "#FF5252",
    "dribble": "#FFD740",
    "tackle": "#69F0AE",
    "interception": "#00E676",
    "clearance": "#B2FF59",
    "block": "#AED581",
    "aerial_duel": "#CE93D8",
    "ground_duel": "#BA68C8",
    "ball_recovery": "#4DB6AC",
    "possession_lost": "#FF8A65",
    "foul_committed": "#E57373",
    "foul_won": "#F06292",
    "card": "#FFEB3B",
    "save": "#90CAF9",
}


def lab_to_bgr(lab: np.ndarray) -> BGR:
    pixel = np.array([[lab]], dtype=np.float32)
    bgr = cv2.cvtColor(pixel, cv2.COLOR_Lab2BGR)[0, 0]
    return tuple(int(np.clip(c * 255, 0, 255)) for c in bgr)


def bgr_to_hex(bgr: BGR) -> str:
    b, g, r = bgr
    return f"#{r:02x}{g:02x}{b:02x}"


def readable_text_color(bgr: BGR) -> BGR:
    b, g, r = bgr
    return (0, 0, 0) if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else (255, 255, 255)


def ensure_visible(bgr: BGR, min_value: float = 0.35) -> BGR:
    """Brightens very dark kit colours so they stay visible when drawn on grass."""
    b, g, r = (c / 255 for c in bgr)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if v < min_value:
        r, g, b = colorsys.hsv_to_rgb(h, s, min_value)
    return int(b * 255), int(g * 255), int(r * 255)


def describe_color(bgr: BGR) -> str:
    """Plain-English kit colour, used to tell Gemini which team to look at."""
    b, g, r = (c / 255 for c in bgr)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360
    if v < 0.22:
        return "black"
    if s < 0.18:
        if v > 0.78:
            return "white"
        return "light grey" if v > 0.5 else "dark grey"
    dark = v < 0.45
    if hue < 15 or hue >= 345:
        return "maroon" if dark else "red"
    if hue < 40:
        return "brown" if dark else "orange"
    if hue < 70:
        return "olive" if dark else "yellow"
    if hue < 165:
        return "dark green" if dark else "green"
    if hue < 200:
        return "teal" if dark else "sky blue"
    if hue < 255:
        return "navy blue" if dark else "blue"
    if hue < 290:
        return "purple"
    return "dark pink" if dark else "pink"
