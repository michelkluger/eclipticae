"""Tests for command-line behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ecliptica.cli import main
from ecliptica.export import save_event
from ecliptica.models import EclipseEvent


def test_compute_command_writes_json() -> None:
    """Compute command should write output JSON and return success."""
    with TemporaryDirectory() as temp_dir:
        out_path = Path(temp_dir) / "computed.json"
        exit_code = main(
            [
                "compute",
                "--lat",
                "40.4168",
                "--lon",
                "-3.7038",
                "--date",
                "2026-01-01",
                "--out",
                str(out_path),
            ],
        )
        path_exists = out_path.exists()

    if exit_code != 0:
        raise AssertionError
    if not path_exists:
        raise AssertionError


def test_render_command_dispatches_to_renderer() -> None:
    """Render command should forward scene parameters to renderer."""
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
    captured: dict[str, object] = {}

    def fake_render(  # noqa: PLR0913
        event_arg: EclipseEvent,
        out_arg: str | Path,
        *,
        quality: str,
        scene: str,
        preview: bool,
        disable_caching: bool,
    ) -> Path:
        out_path = Path(out_arg)
        captured["event"] = event_arg
        captured["out"] = out_path
        captured["quality"] = quality
        captured["scene"] = scene
        captured["preview"] = preview
        captured["disable_caching"] = disable_caching
        return out_path

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "event.json"
        output_path = temp_path / "map.mp4"
        save_event(event, input_path)

        with patch("ecliptica.cli.render_scene", side_effect=fake_render):
            exit_code = main(
                [
                    "render",
                    "--input",
                    str(input_path),
                    "--out",
                    str(output_path),
                    "--quality",
                    "high",
                    "--scene",
                    "map",
                    "--preview",
                ],
            )

    if exit_code != 0:
        raise AssertionError
    _expect_equal(captured.get("event"), event, "event")
    _expect_equal(captured.get("out"), output_path, "out")
    _expect_equal(captured.get("quality"), "high", "quality")
    _expect_equal(captured.get("scene"), "map", "scene")
    if captured.get("preview") is not True:
        raise AssertionError
    if captured.get("disable_caching") is not False:
        raise AssertionError


def _expect_equal(actual: object, expected: object, label: str) -> None:
    del label
    if actual != expected:
        raise AssertionError
