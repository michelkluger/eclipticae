"""Shared constants used by the rendering subsystem."""

from __future__ import annotations

from pathlib import Path

QUALITY_SHORTCUT = {
    "low": "l",
    "medium": "m",
    "high": "h",
    "production": "p",
    "4k": "k",
}

SUPPORTED_SCENES = {
    "map": "WorldMapScene",
    "globe": "GlobeShadowScene",
}

EARTH_RADIUS_KM = 6378.137
AU_KM = 149597870.7
EARTH_RADIUS_AU = EARTH_RADIUS_KM / AU_KM

COASTLINE_ASSET_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "ne_110m_coastline.geojson"
)
