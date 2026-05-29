# Shared utility functions (path resolution, formatting, etc.).
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return an absolute path to a bundled resource.

    When running from source the path is resolved relative to the repository
    root (three levels above this file: src/utils/__init__.py → src/ → repo).
    When running as a PyInstaller-frozen executable, PyInstaller extracts all
    bundled data files into a temporary directory exposed via ``sys._MEIPASS``;
    the same relative structure is preserved there.

    Usage::

        from utils import resource_path
        logo = resource_path("assets", "images", "logo.png")
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[2]))
    return base.joinpath(*parts)
