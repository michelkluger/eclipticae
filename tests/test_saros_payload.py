"""Tests for Saros multi-year payload generation."""

from __future__ import annotations

from eclipticae.render.saros_payload import build_saros_scene_payload

_SAROS_YEAR = 2026
_MIN_PATH_POINTS = 2


def test_build_saros_scene_payload_contains_events_and_paths() -> None:
    """Saros payload should include events with centerline and limit paths."""
    payload = build_saros_scene_payload(
        year=_SAROS_YEAR,
        name="annular",
        years=2,
        preview=True,
    )
    events = payload.get("events", [])
    if not isinstance(events, list) or len(events) < 1:
        raise AssertionError

    first_event = events[0]
    if "saros_offset" not in first_event:
        raise AssertionError
    if "saros_phase_days" not in first_event:
        raise AssertionError
    path = first_event.get("path", {})
    for key in ("centerline", "penumbra_north", "penumbra_south", "core_north", "core_south"):
        points = path.get(key)
        if not isinstance(points, list) or len(points) < _MIN_PATH_POINTS:
            raise AssertionError
