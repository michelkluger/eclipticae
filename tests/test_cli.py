"""Tests for command-line behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import orjson

from ecliptica.catalog import GlobalEclipseRecord
from ecliptica.cli import _catalog_event_detail, _WizardBackError, main
from ecliptica.export import save_event
from ecliptica.models import EclipseEvent

_EXPECTED_PLAN_CALLS = 2


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


def test_main_without_args_runs_wizard() -> None:
    """No-arg invocation should default to the interactive wizard."""
    with patch("ecliptica.cli.wizard_command") as wizard_mock:
        exit_code = main([])

    if exit_code != 0:
        raise AssertionError
    if wizard_mock.call_count != 1:
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
        renderer: str,
        preview: bool,
        disable_caching: bool,
    ) -> Path:
        out_path = Path(out_arg)
        captured["event"] = event_arg
        captured["out"] = out_path
        captured["quality"] = quality
        captured["scene"] = scene
        captured["renderer"] = renderer
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
    _expect_equal(captured.get("renderer"), "cairo", "renderer")
    if captured.get("preview") is not True:
        raise AssertionError
    if captured.get("disable_caching") is not False:
        raise AssertionError


def test_lookup_command_writes_json_output() -> None:
    """Lookup command should serialize the lookup payload when out is provided."""
    fake_payload = {
        "query": {"year": 2026, "name": "annular"},
        "match": {"name": "2026-02-17 Annular Solar Eclipse"},
        "year_events": [],
        "saros_period_days": 6585.321667,
        "saros_cycle": [],
    }
    with TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "lookup.json"
        with patch("ecliptica.cli.lookup_eclipse_with_saros", return_value=fake_payload):
            exit_code = main(
                [
                    "lookup",
                    "--year",
                    "2026",
                    "--name",
                    "annular",
                    "--out",
                    str(output_path),
                ],
            )
        written = orjson.loads(output_path.read_bytes())

    if exit_code != 0:
        raise AssertionError
    _expect_equal(written, fake_payload, "lookup_payload")


def test_render_saros_command_dispatches_to_renderer() -> None:
    """Render-saros command should forward parameters to Saros renderer."""
    captured: dict[str, object] = {}

    def fake_render_saros(  # noqa: PLR0913
        *,
        year: int,
        name: str,
        output_path: str | Path,
        years: int,
        quality: str,
        renderer: str,
        preview: bool,
        disable_caching: bool,
    ) -> Path:
        out_path = Path(output_path)
        captured["year"] = year
        captured["name"] = name
        captured["output_path"] = out_path
        captured["years"] = years
        captured["quality"] = quality
        captured["renderer"] = renderer
        captured["preview"] = preview
        captured["disable_caching"] = disable_caching
        return out_path

    with TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "saros.mp4"
        with patch("ecliptica.cli.render_saros_scene", side_effect=fake_render_saros):
            exit_code = main(
                [
                    "render-saros",
                    "--year",
                    "2021",
                    "--name",
                    "total",
                    "--years",
                    "20",
                    "--quality",
                    "low",
                    "--out",
                    str(output_path),
                    "--preview",
                ],
            )

    if exit_code != 0:
        raise AssertionError
    _expect_equal(captured.get("year"), 2021, "year")
    _expect_equal(captured.get("name"), "total", "name")
    _expect_equal(captured.get("output_path"), output_path, "output_path")
    _expect_equal(captured.get("years"), 20, "years")
    _expect_equal(captured.get("quality"), "low", "quality")
    _expect_equal(captured.get("renderer"), "cairo", "renderer")
    if captured.get("preview") is not True:
        raise AssertionError
    if captured.get("disable_caching") is not False:
        raise AssertionError


def test_wizard_generates_render_command_text() -> None:
    """Wizard should emit a runnable render command from guided prompts."""
    with (
        patch(
            "ecliptica.cli._load_wizard_settings",
            return_value=SimpleNamespace(disable_caching=False),
        ),
        patch(
            "ecliptica.cli._ui_select",
            side_effect=["render", "json_file", "globe", "low", "opengl"],
        ),
        patch("ecliptica.cli._select_event_json_path", return_value="sim_event.json"),
        patch("ecliptica.cli._ui_text", side_effect=["preview.mp4"]),
        patch("ecliptica.cli._ui_confirm", side_effect=[False]) as confirm_mock,
        patch("ecliptica.cli.typer.echo") as echo_mock,
    ):
        exit_code = main(["wizard"])

    if exit_code != 0:
        raise AssertionError

    rendered_lines = [
        call.args[0]
        for call in echo_mock.call_args_list
        if call.args and isinstance(call.args[0], str)
    ]
    expected = (
        "ecliptica render --input sim_event.json --out preview.mp4 --renderer opengl "
        "--quality low --scene globe --preview"
    )
    if expected not in rendered_lines:
        raise AssertionError
    first_confirm = confirm_mock.call_args_list[0]
    if first_confirm.kwargs.get("default") is not True:
        raise AssertionError


def test_wizard_lookup_skips_out_flag_when_empty() -> None:
    """Wizard lookup command should omit --out when user leaves it blank."""
    with (
        patch(
            "ecliptica.cli._load_wizard_settings",
            return_value=SimpleNamespace(disable_caching=False),
        ),
        patch("ecliptica.cli._ui_select", side_effect=["lookup"]),
        patch("ecliptica.cli._ui_int", side_effect=[2026, 2, 45]),
        patch("ecliptica.cli._ui_text", side_effect=["annular", ""]),
        patch("ecliptica.cli._ui_confirm", side_effect=[False]),
        patch("ecliptica.cli.typer.echo") as echo_mock,
    ):
        exit_code = main(["wizard"])

    if exit_code != 0:
        raise AssertionError

    rendered_lines = [
        call.args[0]
        for call in echo_mock.call_args_list
        if call.args and isinstance(call.args[0], str)
    ]
    matches = [line for line in rendered_lines if line.startswith("ecliptica lookup ")]
    if len(matches) != 1:
        raise AssertionError
    if "--out" in matches[0]:
        raise AssertionError


def test_wizard_render_from_catalog_emits_compute_and_render() -> None:
    """Catalog source render flow should emit compute and render commands."""
    event = GlobalEclipseRecord(
        eclipse_id="20260217-annular",
        name="2026-02-17 Annular Solar Eclipse",
        event_kind="annular",
        peak_utc=datetime(2026, 2, 17, 12, 0, tzinfo=UTC),
        latitude=-59.2,
        longitude=-24.8,
        distance_km=381234.0,
        obscuration=0.94,
    )
    with (
        patch(
            "ecliptica.cli._load_wizard_settings",
            return_value=SimpleNamespace(disable_caching=False),
        ),
        patch(
            "ecliptica.cli._ui_select",
            side_effect=["render", "catalog_year", "map", "low"],
        ),
        patch("ecliptica.cli._select_catalog_event", return_value=event),
        patch("ecliptica.cli._ui_text", side_effect=["catalog_event.json", "map.mp4"]),
        patch("ecliptica.cli._ui_confirm", side_effect=[False]),
        patch("ecliptica.cli.typer.echo") as echo_mock,
    ):
        exit_code = main(["wizard"])

    if exit_code != 0:
        raise AssertionError

    rendered_lines = [
        call.args[0]
        for call in echo_mock.call_args_list
        if call.args and isinstance(call.args[0], str)
    ]
    if not any(line.startswith("  1. ecliptica compute ") for line in rendered_lines):
        raise AssertionError
    if not any(line.startswith("  2. ecliptica render ") for line in rendered_lines):
        raise AssertionError
    if not any("--renderer cairo" in line for line in rendered_lines):
        raise AssertionError


def test_wizard_render_saros_uses_selected_anchor_event() -> None:
    """Saros wizard should use selected anchor eclipse name and Cairo renderer."""
    anchor = GlobalEclipseRecord(
        eclipse_id="20260812-total",
        name="2026-08-12 Total Solar Eclipse",
        event_kind="total",
        peak_utc=datetime(2026, 8, 12, 17, 46, tzinfo=UTC),
        latitude=65.2,
        longitude=-25.2,
        distance_km=379012.0,
        obscuration=1.0,
    )
    with (
        patch(
            "ecliptica.cli._load_wizard_settings",
            return_value=SimpleNamespace(disable_caching=False),
        ),
        patch("ecliptica.cli._ui_select", side_effect=["render-saros", "low"]),
        patch("ecliptica.cli._select_anchor_event_for_saros", return_value=anchor),
        patch("ecliptica.cli._ui_text", side_effect=["saros2.mp4"]),
        patch("ecliptica.cli._ui_int", side_effect=[200]),
        patch("ecliptica.cli._ui_confirm", side_effect=[False]),
        patch("ecliptica.cli.typer.echo") as echo_mock,
    ):
        exit_code = main(["wizard"])

    if exit_code != 0:
        raise AssertionError
    rendered_lines = [
        call.args[0]
        for call in echo_mock.call_args_list
        if call.args and isinstance(call.args[0], str)
    ]
    expected = (
        "ecliptica render-saros --year 2026 --name "
        "'2026-08-12 Total Solar Eclipse' --out saros2.mp4 --years 200 "
        "--renderer cairo --quality low --preview"
    )
    if expected not in rendered_lines:
        raise AssertionError


def test_catalog_event_detail_handles_nan_obscuration() -> None:
    """Catalog detail should render NaN obscuration values as n/a."""
    event = GlobalEclipseRecord(
        eclipse_id="20280722-total",
        name="2028-07-22 Total Solar Eclipse",
        event_kind="total",
        peak_utc=datetime(2028, 7, 22, 8, 0, tzinfo=UTC),
        latitude=-15.6,
        longitude=126.7,
        distance_km=378000.0,
        obscuration=float("nan"),
    )
    detail = _catalog_event_detail(event)
    if detail != "greatest eclipse, obscuration n/a":
        raise AssertionError


def test_wizard_back_returns_to_task_menu() -> None:
    """Back from a task plan should return to task selection without exiting wizard."""
    with (
        patch(
            "ecliptica.cli._load_wizard_settings",
            return_value=SimpleNamespace(disable_caching=False),
        ),
        patch("ecliptica.cli._ui_select", side_effect=["render", "lookup"]),
        patch(
            "ecliptica.cli._plan_for_task",
            side_effect=[
                _WizardBackError(),
                SimpleNamespace(commands=[["lookup", "--year", "2026"]]),
            ],
        ) as plan_mock,
        patch("ecliptica.cli._ui_confirm", side_effect=[False]),
    ):
        exit_code = main(["wizard"])

    if exit_code != 0:
        raise AssertionError
    if plan_mock.call_count != _EXPECTED_PLAN_CALLS:
        raise AssertionError


def _expect_equal(actual: object, expected: object, label: str) -> None:
    del label
    if actual != expected:
        raise AssertionError
