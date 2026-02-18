"""Command-line entry points for ecliptica."""

from __future__ import annotations

import sys
from typing import Annotated, Literal

import click
import typer

from ecliptica.compute import compute_site_eclipse
from ecliptica.export import load_event, save_event
from ecliptica.render import render_scene

QualityName = Literal["low", "medium", "high", "production", "4k", "l", "m", "h", "p", "k"]
SceneName = Literal["map", "globe"]

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Compute and render solar eclipse visualizations.",
)


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
        typer.Option("--input", help="Input event JSON produced by `ecliptica compute`."),
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
            preview=preview,
            disable_caching=disable_caching,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote rendered animation to {output}")


def main(argv: list[str] | None = None) -> int:
    """Run the ecliptica CLI."""
    cli_args = list(argv) if argv is not None else None
    try:
        app(args=cli_args, prog_name="ecliptica", standalone_mode=False)
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
