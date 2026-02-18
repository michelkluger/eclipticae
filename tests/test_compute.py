"""Tests for core eclipse computations."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

from ecliptica.compute import build_timeline, compute_site_eclipse
from ecliptica.models import EclipseEvent

_MIN_TIMELINE_POINTS = 2


def test_compute_site_eclipse_returns_ordered_times() -> None:
    """Returned event times should be internally consistent and UTC-aware."""
    event = compute_site_eclipse(
        latitude=40.4168,
        longitude=-3.7038,
        date_or_datetime="2026-01-01",
        elevation_m=667.0,
    )

    if event.event_kind not in {"partial", "annular", "total", "unknown"}:
        raise AssertionError
    if not (0.0 <= event.obscuration <= 1.0):
        raise AssertionError
    if event.peak_utc.tzinfo != UTC:
        raise AssertionError

    if event.partial_begin_utc is not None and event.partial_begin_utc > event.peak_utc:
        raise AssertionError
    if event.partial_end_utc is not None and event.peak_utc > event.partial_end_utc:
        raise AssertionError


def test_build_timeline_is_monotonic() -> None:
    """Timeline samples should progress forward in time and progress value."""
    event = EclipseEvent(
        latitude=0.0,
        longitude=0.0,
        elevation_m=0.0,
        search_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        event_kind="partial",
        obscuration=0.5,
        peak_utc=datetime(2026, 1, 1, 12, 15, tzinfo=UTC),
        peak_altitude_deg=42.0,
        partial_begin_utc=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        partial_end_utc=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        total_begin_utc=None,
        total_end_utc=None,
    )
    points = build_timeline(event, step_minutes=10)

    if len(points) < _MIN_TIMELINE_POINTS:
        raise AssertionError
    if points[0].progress != 0.0:
        raise AssertionError
    if points[-1].progress != 1.0:
        raise AssertionError

    if not all(left.utc <= right.utc for left, right in pairwise(points)):
        raise AssertionError
    if not all(left.progress <= right.progress for left, right in pairwise(points)):
        raise AssertionError


def test_build_timeline_rejects_non_positive_step() -> None:
    """Non-positive step size should raise ValueError."""
    event = EclipseEvent(
        latitude=0.0,
        longitude=0.0,
        elevation_m=0.0,
        search_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        event_kind="partial",
        obscuration=0.5,
        peak_utc=datetime(2026, 1, 1, 12, 15, tzinfo=UTC),
        peak_altitude_deg=42.0,
        partial_begin_utc=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        partial_end_utc=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        total_begin_utc=None,
        total_end_utc=None,
    )

    try:
        build_timeline(event, step_minutes=0)
    except ValueError as exc:
        if "step_minutes" not in str(exc):
            raise AssertionError from exc
    else:
        raise AssertionError
