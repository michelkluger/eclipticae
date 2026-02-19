"""Tests for render payload generation."""

from __future__ import annotations

from datetime import UTC, datetime

from ecliptica.models import EclipseEvent
from ecliptica.render.payload import build_scene_payload

_MIN_SAMPLE_COUNT = 2


def test_build_scene_payload_map_includes_expected_fields() -> None:
    """Map payload should include event metadata, samples, coastlines, and land."""
    event = _sample_event()
    payload = build_scene_payload(event, "map")

    if payload["scene"] != "map":
        raise AssertionError
    if "event" not in payload:
        raise AssertionError
    if "samples" not in payload:
        raise AssertionError
    if "coastline_segments" not in payload:
        raise AssertionError
    if "land_polygons" not in payload:
        raise AssertionError

    samples = payload["samples"]
    if not isinstance(samples, list) or len(samples) < _MIN_SAMPLE_COUNT:
        raise AssertionError

    required_keys = {
        "seconds",
        "utc",
        "sun_lon",
        "sun_lat",
        "shadow_lon",
        "shadow_lat",
        "shadow_hits_earth",
        "shadow_miss_km",
        "penumbra_radius_km",
        "core_radius_km",
        "core_kind",
        "penumbra_north_lon",
        "penumbra_north_lat",
        "penumbra_south_lon",
        "penumbra_south_lat",
        "core_north_lon",
        "core_north_lat",
        "core_south_lon",
        "core_south_lat",
    }
    if not required_keys.issubset(samples[0]):
        raise AssertionError

    land_polygons = payload["land_polygons"]
    if not isinstance(land_polygons, list) or not land_polygons:
        raise AssertionError


def test_preview_payload_is_smaller_than_default_payload() -> None:
    """Preview payload should reduce sample, coastline, and land point density."""
    event = _sample_event()

    default_payload = build_scene_payload(event, "map", preview=False)
    preview_payload = build_scene_payload(event, "map", preview=True)

    default_samples = default_payload["samples"]
    preview_samples = preview_payload["samples"]
    if len(preview_samples) >= len(default_samples):
        raise AssertionError

    default_coast_points = _count_geo_points(default_payload["coastline_segments"])
    preview_coast_points = _count_geo_points(preview_payload["coastline_segments"])
    if preview_coast_points >= default_coast_points:
        raise AssertionError

    default_land_points = _count_geo_points(default_payload["land_polygons"])
    preview_land_points = _count_geo_points(preview_payload["land_polygons"])
    if preview_land_points >= default_land_points:
        raise AssertionError


def _sample_event() -> EclipseEvent:
    return EclipseEvent(
        latitude=40.4168,
        longitude=-3.7038,
        elevation_m=667.0,
        search_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        event_kind="partial",
        obscuration=0.42,
        peak_utc=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        peak_altitude_deg=22.2,
        partial_begin_utc=datetime(2026, 1, 1, 11, 30, tzinfo=UTC),
        partial_end_utc=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        total_begin_utc=None,
        total_end_utc=None,
    )


def _count_geo_points(segments: object) -> int:
    if not isinstance(segments, list):
        return 0
    total = 0
    for segment in segments:
        if isinstance(segment, list):
            total += len(segment)
    return total
