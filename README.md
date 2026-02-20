# ecliptica

<img width="1617" height="854" alt="image" src="https://github.com/user-attachments/assets/4335f81b-c1d2-458e-81fb-b5c3cf1a2571" />


`ecliptica` is a Python library + CLI to compute local solar eclipse circumstances and render eclipse animations with Manim.

[![CI](https://github.com/michelkluger/ecliptica/actions/workflows/ci.yml/badge.svg)](https://github.com/michelkluger/ecliptica/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## MVP Features

- Compute the next local eclipse from a start date (`partial`, `annular`, or `total`).
- Export eclipse metadata to JSON.
- Render 2D map or 3D globe `.mp4` animations from exported JSON.
- Preview mode for faster iteration (`--preview`) and optional render cache control (`--disable-caching`).

## Install

```bash
uv sync
```

Linux prerequisite packages for Manim (needed before `uv sync`):

```bash
sudo apt-get update
sudo apt-get install -y pkg-config libcairo2-dev libpango1.0-dev ffmpeg
```

## CLI Usage

Compute an event:

```bash
uv run ecliptica compute --lat 40.4168 --lon -3.7038 --date 2026-01-01 --out event.json
```

Render world map shadow video (default scene):

```bash
uv run ecliptica render --input event.json --out eclipse_map.mp4 --quality high
```

Render fast preview while iterating on visuals:

```bash
uv run ecliptica render --input event.json --out eclipse_preview.mp4 --scene map --preview --quality low
```

Render 3D globe scene:

```bash
uv run ecliptica render --input event.json --out eclipse_globe.mp4 --quality high --scene globe
```

Render a multi-year Saros-style sequence with dimmed historical traces:

```bash
uv run ecliptica render-saros --year 2021 --name total --years 20 --out saros_paths.mp4 --quality high
```

Lookup a global eclipse by year/name and include a combined Saros chain:

```bash
uv run ecliptica lookup --year 2026 --name annular --out eclipse_lookup.json
```

Use the interactive wizard to build commands step-by-step:

```bash
uv run ecliptica wizard
```

Wizard highlights:
- Arrow-key menus in interactive terminals.
- Render from an existing event JSON or pick upcoming eclipses from a chosen year.
- For `render-saros`, choose the anchor eclipse from that year (no manual anchor-name typing).
- Adaptive defaults: low quality recommends preview mode and prefers faster renderer options.
- Global wizard setting for caching default, so you don't need to answer that every run.
- Back navigation inside wizard: choose `Back` in menus or use `Esc`/`Ctrl+C`.
- Outputs exact command(s) and can run them immediately.

Renderer note:
- `opengl` is currently supported for `--scene globe` renders.
- `map` and `render-saros` use `cairo`.

## Python Usage

```python
from ecliptica import compute_site_eclipse, render_scene, save_event

event = compute_site_eclipse(
    latitude=40.4168,
    longitude=-3.7038,
    date_or_datetime="2026-01-01",
    elevation_m=667,
)
save_event(event, "event.json")
render_scene(event, "eclipse_map.mp4", quality="high", scene="map")
```

## Dev Commands

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest
```

Install pre-commit hooks:

```bash
uv run pre-commit install
```

Run all checks at once (PowerShell):

```powershell
.\scripts\check_all.ps1
```

## Project Docs

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
