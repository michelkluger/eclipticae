# ecliptica

`ecliptica` is a Python library + CLI to compute local solar eclipse circumstances and render eclipse animations with Manim.

## MVP Features

- Compute the next local eclipse from a start date (`partial`, `annular`, or `total`).
- Export eclipse metadata to JSON.
- Render 2D map or 3D globe `.mp4` animations from exported JSON (optional `viz` extra).
- Preview mode for faster iteration (`--preview`) and optional render cache control (`--disable-caching`).

## Install

```bash
uv sync
```

Optional rendering extras:

```bash
uv sync --extra viz
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
