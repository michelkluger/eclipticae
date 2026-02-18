"""Generate Manim scene source strings for each render scene type."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ecliptica.render.globe_script_builder import build_globe_script
from ecliptica.render.map_script_builder import build_map_script

if TYPE_CHECKING:
    from pathlib import Path


def build_manim_script(payload_path: Path, scene: str) -> str:
    """Build the full Python script for the requested scene."""
    if scene == "map":
        return build_map_script(payload_path)
    if scene == "globe":
        return build_globe_script(payload_path)
    msg = f"Unsupported scene: {scene}"
    raise ValueError(msg)
