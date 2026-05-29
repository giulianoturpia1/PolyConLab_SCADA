"""
Color palette shared across all UI modules.
Import as:  from ui import palette as col
"""

from __future__ import annotations

BG = "#1E2127"
PANEL = "#282C34"
BORDER = "#3D4452"
TEXT = "#ABB2BF"
WHITE = "#EFEFEF"
GREEN = "#56B870"
RED = "#E06C75"
ORANGE = "#E5C07B"
BLUE = "#61AFEF"
GRAY = "#5C6370"

STATE_COLOR: dict[str, str] = {
    "STARTUP": BLUE,
    "CHECKUP": ORANGE,
    "MANUAL": GREEN,
    "PAUSE": ORANGE,
    "SOFT ERROR": "#D19A66",
    "HARD ERROR": RED,
    "SHUTDOWN": GRAY,
}
