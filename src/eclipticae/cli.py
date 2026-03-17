"""Command-line entry points for eclipticae."""

from __future__ import annotations

import json
import math
import shlex
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Annotated, Literal

import click
import orjson
import typer

from eclipticae.catalog import (
    GlobalEclipseRecord,
    list_global_solar_eclipses,
    lookup_eclipse_with_saros,
)
from eclipticae.cli_ui import (
    _MenuOption,
    _ui_confirm,
    _ui_float,
    _ui_int,
    _ui_select,
    _ui_text,
    _WizardBackError,
)
from eclipticae.compute import compute_site_eclipse
from eclipticae.export import load_event, save_event
from eclipticae.render import render_saros_scene, render_scene

QualityName = Literal[
    "very-low",
    "vl",
    "low",
    "medium",
    "high",
    "production",
    "4k",
    "l",
    "m",
    "h",
    "p",
    "k",
]
SceneName = Literal["map", "globe"]
RendererName = Literal["cairo", "opengl"]
WizardCommand = Literal["compute", "render", "lookup", "render-saros"]
_CUSTOM_PATH_SENTINEL = "__custom_path__"
_CATALOG_SOURCE = "catalog_year"
_JSON_SOURCE = "json_file"
_DEFAULT_UPCOMING_COUNT = 8
_WIZARD_SETTINGS_KEY = "__wizard_settings__"
_WIZARD_SETTINGS_PATH = Path.home() / ".eclipticae" / "wizard_settings.json"
_SETTINGS_CACHING_KEY = "__settings_caching__"


@dataclass(frozen=True, slots=True)
class _WizardPlan:
    commands: list[list[str]]


@dataclass(frozen=True, slots=True)
class _WizardSettings:
    disable_caching: bool = False


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="Compute and render solar eclipse visualizations.",
)


@app.callback(invoke_without_command=True)
def app_callback(context: typer.Context) -> None:
    """Launch the interactive wizard when no subcommand is provided."""
    if context.invoked_subcommand is not None:
        return
    wizard_command()


@app.command("compute")
def compute_command(
    lat: Annotated[float, typer.Option("--lat", help="Observer latitude in degrees.")],
    lon: Annotated[float, typer.Option("--lon", help="Observer longitude in degrees.")],
    date: Annotated[str, typer.Option("--date", help="ISO date or datetime in UTC.")],
    out: Annotated[str, typer.Option("--out", help="Path to write computed event JSON.")],
    elevation_m: Annotated[
        float,
        typer.Option("--elevation-m", help="Observer elevation in meters."),
    ] = 0.0,
) -> None:
    """Compute the next local solar eclipse from a start date."""
    try:
        event = compute_site_eclipse(
            latitude=lat,
            longitude=lon,
            date_or_datetime=date,
            elevation_m=elevation_m,
        )
        output = save_event(event, out)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote eclipse event JSON to {output}")


@app.command("render")
def render_command(  # noqa: PLR0913
    input_path: Annotated[
        str,
        typer.Option("--input", help="Input event JSON produced by `eclipticae compute`."),
    ],
    out: Annotated[str, typer.Option("--out", help="Destination mp4 path.")],
    quality: Annotated[
        QualityName,
        typer.Option("--quality", help="Manim quality preset."),
    ] = "high",
    scene: Annotated[
        SceneName,
        typer.Option("--scene", help="Scene type to render."),
    ] = "map",
    renderer: Annotated[
        RendererName,
        typer.Option("--renderer", help="Manim backend renderer."),
    ] = "cairo",
    *,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            help="Faster preview mode (fewer payload samples + lower render fps).",
        ),
    ] = False,
    disable_caching: Annotated[
        bool,
        typer.Option(
            "--disable-caching",
            help="Disable Manim frame caching for deterministic clean renders.",
        ),
    ] = False,
) -> None:
    """Render a Manim mp4 eclipse visualization from computed eclipse JSON."""
    try:
        event = load_event(input_path)
        output = render_scene(
            event,
            out,
            quality=quality,
            scene=scene,
            renderer=renderer,
            preview=preview,
            disable_caching=disable_caching,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote rendered animation to {output}")


@app.command("lookup")
def lookup_command(
    year: Annotated[
        int,
        typer.Option("--year", help="UTC year to search in the global eclipse catalog."),
    ],
    name: Annotated[
        str,
        typer.Option(
            "--name",
            help="Name query (for example: 'total', '2026-08', 'annular').",
        ),
    ],
    out: Annotated[
        str | None,
        typer.Option(
            "--out",
            help="Optional output path. If omitted, the JSON payload is printed.",
        ),
    ] = None,
    saros_span: Annotated[
        int,
        typer.Option(
            "--saros-span",
            help="How many Saros steps before/after to include around the match.",
        ),
    ] = 2,
    window_days: Annotated[
        int,
        typer.Option(
            "--window-days",
            help="Search window around each Saros target date for nearest eclipse.",
        ),
    ] = 45,
) -> None:
    """Lookup a global eclipse by name/year and show a combined Saros chain."""
    try:
        payload = lookup_eclipse_with_saros(
            year=year,
            name=name,
            saros_span=saros_span,
            window_days=window_days,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    json_payload = orjson.dumps(payload, option=orjson.OPT_INDENT_2) + b"\n"
    if out is None:
        typer.echo(json_payload.decode("utf-8"))
        return

    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(json_payload)
    typer.echo(f"Wrote eclipse lookup JSON to {output_path}")


@app.command("render-saros")
def render_saros_command(  # noqa: PLR0913
    year: Annotated[
        int,
        typer.Option("--year", help="Start UTC year for the multi-year Saros map."),
    ],
    name: Annotated[
        str,
        typer.Option(
            "--name",
            help="Anchor event query used to compute Saros offsets.",
        ),
    ],
    out: Annotated[str, typer.Option("--out", help="Destination mp4 path.")],
    years: Annotated[
        int,
        typer.Option("--years", help="Number of years to include in sequence."),
    ] = 20,
    quality: Annotated[
        QualityName,
        typer.Option("--quality", help="Manim quality preset."),
    ] = "high",
    renderer: Annotated[
        RendererName,
        typer.Option("--renderer", help="Manim backend renderer."),
    ] = "cairo",
    *,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            help="Faster preview mode (reduced payload sampling and lower render fps).",
        ),
    ] = False,
    disable_caching: Annotated[
        bool,
        typer.Option(
            "--disable-caching",
            help="Disable Manim frame caching for deterministic clean renders.",
        ),
    ] = False,
) -> None:
    """Render a multi-year path animation with Saros offset metadata."""
    try:
        output = render_saros_scene(
            year=year,
            name=name,
            output_path=out,
            years=years,
            quality=quality,
            renderer=renderer,
            preview=preview,
            disable_caching=disable_caching,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote Saros animation to {output}")


@app.command("wizard")
def wizard_command() -> None:
    """Guide users through prompts and output the exact CLI command to run."""
    typer.echo("Ecliptica command builder")
    settings = _load_wizard_settings()
    while True:
        command_name, settings = _choose_task_and_settings(settings)
        try:
            plan = _plan_for_task(command_name, settings)
        except _WizardBackError:
            typer.echo("Back to task menu.")
            continue
        _show_plan_commands(plan)
        try:
            should_run = _ui_confirm("Run it now?", default=True, allow_back=True)
        except _WizardBackError:
            typer.echo("Back to task menu.")
            continue
        if should_run:
            _run_plan_commands(plan)
        return


def _choose_task_and_settings(
    settings: _WizardSettings,
) -> tuple[str, _WizardSettings]:
    while True:
        command_name = _ui_select(
            "Step 1/2 - Choose task",
            options=[
                _MenuOption("render", "Render eclipse animation", "event JSON -> MP4"),
                _MenuOption("compute", "Compute eclipse event", "site + UTC date -> JSON"),
                _MenuOption("lookup", "Lookup global eclipse + Saros", "catalog query -> JSON"),
                _MenuOption(
                    "render-saros",
                    "Render Saros sequence",
                    "year/name -> multi-year MP4",
                ),
                _MenuOption(
                    _WIZARD_SETTINGS_KEY,
                    "Wizard settings",
                ),
            ],
            default_key="render",
        )
        if command_name != _WIZARD_SETTINGS_KEY:
            return command_name, settings
        try:
            settings = _wizard_edit_settings(settings)
        except _WizardBackError:
            continue


def _show_plan_commands(plan: _WizardPlan) -> None:
    rendered_commands = [_shell_join(["eclipticae", *args]) for args in plan.commands]
    typer.echo("")
    if len(rendered_commands) == 1:
        typer.echo("Generated command:")
        typer.echo(rendered_commands[0])
        return
    typer.echo("Generated commands:")
    for index, command_text in enumerate(rendered_commands, start=1):
        typer.echo(f"  {index}. {command_text}")
    typer.echo("Combined:")
    typer.echo(" && ".join(rendered_commands))


def _run_plan_commands(plan: _WizardPlan) -> None:
    for args in plan.commands:
        exit_code = main(args)
        if exit_code != 0:
            raise typer.Exit(code=exit_code)


def _plan_for_task(task: str, settings: _WizardSettings) -> _WizardPlan:
    if task == "compute":
        return _wizard_compute_plan()
    if task == "render":
        return _wizard_render_plan(settings)
    if task == "lookup":
        return _wizard_lookup_plan()
    return _wizard_render_saros_plan(settings)


def _wizard_compute_plan() -> _WizardPlan:
    typer.echo("")
    typer.echo("Step 2/2 - Configure `compute`")
    lat = _ui_float("Latitude (degrees)", allow_back=True)
    lon = _ui_float("Longitude (degrees)", allow_back=True)
    date = _ui_text("Start date/time in UTC", default="2026-01-01", allow_back=True)
    out = _ui_text("Output JSON path", default="event.json", allow_back=True)
    elevation_m = _ui_float("Elevation in meters", default=0.0, allow_back=True)

    args = [
        "compute",
        "--lat",
        str(lat),
        "--lon",
        str(lon),
        "--date",
        date,
        "--out",
        out,
    ]
    if elevation_m != 0.0:
        args.extend(["--elevation-m", str(elevation_m)])
    return _WizardPlan(commands=[args])


def _wizard_render_plan(settings: _WizardSettings) -> _WizardPlan:
    typer.echo("")
    typer.echo("Step 2/2 - Configure `render`")
    source = _ui_select(
        "Event source",
        options=[
            _MenuOption(_JSON_SOURCE, "Use existing event JSON", "render from local file"),
            _MenuOption(_CATALOG_SOURCE, "Pick from eclipse catalog by year", "build event first"),
        ],
        default_key=_JSON_SOURCE,
        allow_back=True,
    )
    pre_commands: list[list[str]] = []
    if source == _CATALOG_SOURCE:
        selected_event = _select_catalog_event()
        default_output = f"{selected_event.eclipse_id}.json"
        input_path = _ui_text(
            "Intermediate event JSON output",
            default=default_output,
            allow_back=True,
        )
        pre_commands.append(
            _build_compute_from_global_record_command(
                selected_event,
                output_path=input_path,
            ),
        )
    else:
        input_path = _select_event_json_path()

    scene = _ui_select(
        "Scene type",
        options=[
            _MenuOption("map", "2D world map", "flat map with path products"),
            _MenuOption("globe", "3D globe", "rotating Earth with shadow cone"),
        ],
        default_key="map",
        allow_back=True,
    )
    out = _ui_text("Output MP4 path", default=f"{scene}.mp4", allow_back=True)
    quality = _ui_select(
        "Quality preset",
        options=[
            _MenuOption("very-low", "very-low", "426x240 @ 12fps (fastest)"),
            _MenuOption("low", "low", "854x480 @ 15fps"),
            _MenuOption("medium", "medium", "1280x720 @ 30fps"),
            _MenuOption("high", "high", "1920x1080 @ 60fps"),
            _MenuOption("production", "production", "2560x1440 @ 60fps"),
            _MenuOption("4k", "4k", "3840x2160 @ 60fps"),
        ],
        default_key="high",
        allow_back=True,
    )
    if scene == "globe":
        renderer_default = "opengl" if quality in {"very-low", "low"} else "cairo"
        renderer = _ui_select(
            "Renderer backend",
            options=[
                _MenuOption("opengl", "OpenGL", "usually faster for previews"),
                _MenuOption("cairo", "Cairo", "higher stability / compatibility"),
            ],
            default_key=renderer_default,
            allow_back=True,
        )
    else:
        renderer = "cairo"
        typer.echo("Renderer backend: Cairo (OpenGL not supported for map scene yet).")

    preview = quality in {"very-low", "low"}
    typer.echo(
        "Preview mode: enabled (auto for low quality)."
        if preview
        else "Preview mode: disabled (auto for non-low quality).",
    )
    disable_caching = settings.disable_caching
    typer.echo(
        "Caching: disabled (global wizard setting)."
        if disable_caching
        else "Caching: enabled (global wizard setting).",
    )

    args = [
        "render",
        "--input",
        input_path,
        "--out",
        out,
        "--renderer",
        renderer,
        "--quality",
        quality,
        "--scene",
        scene,
    ]
    if preview:
        args.append("--preview")
    if disable_caching:
        args.append("--disable-caching")
    return _WizardPlan(commands=[*pre_commands, args])


def _wizard_lookup_plan() -> _WizardPlan:
    typer.echo("")
    typer.echo("Step 2/2 - Configure `lookup`")
    year = _ui_int("Catalog year", default=datetime.now(tz=UTC).year, allow_back=True)
    name = _ui_text("Name query", default="total", allow_back=True)
    out = _ui_text("Output JSON path (empty = print)", default="", allow_back=True)
    saros_span = _ui_int("Saros span", default=2, allow_back=True)
    window_days = _ui_int("Window days", default=45, allow_back=True)

    args = [
        "lookup",
        "--year",
        str(year),
        "--name",
        name,
        "--saros-span",
        str(saros_span),
        "--window-days",
        str(window_days),
    ]
    if out.strip():
        args.extend(["--out", out.strip()])
    return _WizardPlan(commands=[args])


def _wizard_render_saros_plan(settings: _WizardSettings) -> _WizardPlan:
    typer.echo("")
    typer.echo("Step 2/2 - Configure `render-saros`")
    anchor = _select_anchor_event_for_saros()
    year = anchor.peak_utc.year
    name = anchor.name
    typer.echo(f"Anchor eclipse: {anchor.name}")
    out = _ui_text("Output MP4 path", default="saros.mp4", allow_back=True)
    years = _ui_int("Years to include", default=20, allow_back=True)
    renderer = "cairo"
    typer.echo("Renderer backend: Cairo (OpenGL not supported for render-saros yet).")
    quality = _ui_select(
        "Quality preset",
        options=[
            _MenuOption("very-low", "very-low", "426x240 @ 12fps (fastest)"),
            _MenuOption("low", "low", "854x480 @ 15fps"),
            _MenuOption("medium", "medium", "1280x720 @ 30fps"),
            _MenuOption("high", "high", "1920x1080 @ 60fps"),
            _MenuOption("production", "production", "2560x1440 @ 60fps"),
            _MenuOption("4k", "4k", "3840x2160 @ 60fps"),
        ],
        default_key="high",
        allow_back=True,
    )
    preview = quality in {"very-low", "low"}
    typer.echo(
        "Preview mode: enabled (auto for low quality)."
        if preview
        else "Preview mode: disabled (auto for non-low quality).",
    )
    disable_caching = settings.disable_caching
    typer.echo(
        "Caching: disabled (global wizard setting)."
        if disable_caching
        else "Caching: enabled (global wizard setting).",
    )

    args = [
        "render-saros",
        "--year",
        str(year),
        "--name",
        name,
        "--out",
        out,
        "--years",
        str(years),
        "--renderer",
        renderer,
        "--quality",
        quality,
    ]
    if preview:
        args.append("--preview")
    if disable_caching:
        args.append("--disable-caching")
    return _WizardPlan(commands=[args])


def _wizard_edit_settings(settings: _WizardSettings) -> _WizardSettings:
    typer.echo("")
    section = _ui_select(
        "Wizard settings",
        options=[
            _MenuOption(
                _SETTINGS_CACHING_KEY,
                f"Caching ({'disabled' if settings.disable_caching else 'enabled'})",
                "toggle default caching mode",
            ),
        ],
        default_key=_SETTINGS_CACHING_KEY,
        allow_back=True,
    )
    if section != _SETTINGS_CACHING_KEY:
        return settings

    updated = _WizardSettings(disable_caching=not settings.disable_caching)
    _save_wizard_settings(updated)
    status_text = "disabled" if updated.disable_caching else "enabled"
    status_detail = (
        "clean deterministic rerenders" if updated.disable_caching else "faster, recommended"
    )
    typer.echo(f"Saved wizard settings: Caching ({status_text}) - {status_detail}.")
    typer.echo("")
    return updated


def _load_wizard_settings() -> _WizardSettings:
    if not _WIZARD_SETTINGS_PATH.exists():
        return _WizardSettings()
    try:
        payload = json.loads(_WIZARD_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError):
        return _WizardSettings()
    disable_caching = bool(payload.get("disable_caching", False))
    return _WizardSettings(disable_caching=disable_caching)


def _save_wizard_settings(settings: _WizardSettings) -> None:
    try:
        _WIZARD_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"disable_caching": settings.disable_caching}
        _WIZARD_SETTINGS_PATH.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _select_event_json_path() -> str:
    candidates = sorted(Path.cwd().glob("*.json"))
    options: list[_MenuOption] = []
    default_key = "event.json"
    for path in candidates[:8]:
        options.append(
            _MenuOption(
                key=path.name,
                label=path.name,
                detail="found in current folder",
            ),
        )
        if path.name == "event.json":
            default_key = path.name
    if options and default_key == "event.json" and not Path("event.json").exists():
        default_key = options[0].key
    options.append(
        _MenuOption(
            key=_CUSTOM_PATH_SENTINEL,
            label="Type custom path",
            detail="enter any JSON path manually",
        ),
    )

    selected = _ui_select(
        "Input event JSON",
        options=options,
        default_key=default_key,
        allow_back=True,
    )
    if selected == _CUSTOM_PATH_SENTINEL:
        return _ui_text("Custom event JSON path", default="event.json", allow_back=True)
    return selected


def _select_catalog_event() -> GlobalEclipseRecord:
    while True:
        start_year = _ui_int(
            "Start year for eclipse options",
            default=datetime.now(tz=UTC).year,
            allow_back=True,
        )
        upcoming_count = _ui_int(
            "How many upcoming eclipses to show",
            default=_DEFAULT_UPCOMING_COUNT,
            allow_back=True,
        )
        if upcoming_count < 1:
            typer.echo("Count must be at least 1.")
            continue

        events = _list_upcoming_eclipses_from_year(start_year, count=upcoming_count)
        if not events:
            typer.echo("No eclipses found for that year range. Try another year.")
            continue

        options = [
            _MenuOption(
                key=event.eclipse_id,
                label=_catalog_event_label(event),
                detail=_catalog_event_detail(event),
            )
            for event in events
        ]
        selected_id = _ui_select(
            "Pick an eclipse",
            options=options,
            default_key=options[0].key,
            allow_back=True,
        )
        for event in events:
            if event.eclipse_id == selected_id:
                return event


def _select_anchor_event_for_saros() -> GlobalEclipseRecord:
    while True:
        year = _ui_int("Anchor year", default=datetime.now(tz=UTC).year, allow_back=True)
        events = list_global_solar_eclipses(year)
        if not events:
            typer.echo(f"No global eclipses found in {year}. Try another year.")
            continue
        options = [
            _MenuOption(
                key=event.eclipse_id,
                label=_catalog_event_label(event),
                detail=_catalog_event_detail(event),
            )
            for event in events
        ]
        selected_id = _ui_select(
            "Pick anchor eclipse",
            options=options,
            default_key=options[0].key,
            allow_back=True,
        )
        for event in events:
            if event.eclipse_id == selected_id:
                return event


def _list_upcoming_eclipses_from_year(start_year: int, *, count: int) -> list[GlobalEclipseRecord]:
    events: list[GlobalEclipseRecord] = []
    year = start_year
    max_year = start_year + 12
    while len(events) < count and year <= max_year:
        events.extend(list_global_solar_eclipses(year))
        year += 1
    return events[:count]


def _catalog_event_label(event: GlobalEclipseRecord) -> str:
    return (
        f"{event.peak_utc:%Y-%m-%d} {event.event_kind.title()} "
        f"(lat {event.latitude:.1f}, lon {event.longitude:.1f})"
    )


def _catalog_event_detail(event: GlobalEclipseRecord) -> str:
    obscuration_raw = event.obscuration
    if obscuration_raw is None or math.isnan(obscuration_raw):
        obscuration = "n/a"
    else:
        obscuration = f"{obscuration_raw:.3f}"
    return f"greatest eclipse, obscuration {obscuration}"


def _build_compute_from_global_record_command(
    record: GlobalEclipseRecord,
    *,
    output_path: str,
) -> list[str]:
    return [
        "compute",
        "--lat",
        str(record.latitude),
        "--lon",
        str(record.longitude),
        "--date",
        record.peak_utc.astimezone(UTC).isoformat(),
        "--out",
        output_path,
    ]


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def main(argv: list[str] | None = None) -> int:
    """Run the eclipticae CLI."""
    cli_args = list(argv) if argv is not None else None
    try:
        app(args=cli_args, prog_name="eclipticae", standalone_mode=False)
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return exc.exit_code
    except click.Abort:
        sys.stderr.write("Aborted!\n")
        return 1
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
