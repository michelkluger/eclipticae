"""Tests for JSON import/export helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from eclipticae.export import load_event, save_event
from eclipticae.models import EclipseEvent


def test_save_and_load_event_roundtrip() -> None:
    """Saving and loading should preserve all model fields."""
    event = EclipseEvent(
        latitude=12.34,
        longitude=56.78,
        elevation_m=100.0,
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

    with TemporaryDirectory() as temp_dir:
        out_path = Path(temp_dir) / "event.json"
        save_event(event, out_path)
        loaded = load_event(out_path)

    if loaded != event:
        raise AssertionError
