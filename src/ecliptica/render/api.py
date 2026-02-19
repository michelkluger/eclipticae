"""Runtime rendering API that orchestrates payload and scene generation."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ecliptica.render.constants import QUALITY_SHORTCUT, SUPPORTED_SCENES
from ecliptica.render.payload import build_scene_payload
from ecliptica.render.saros_payload import build_saros_scene_payload
from ecliptica.render.script_builders import build_manim_script

if TYPE_CHECKING:
    from ecliptica.models import EclipseEvent


def render_scene(  # noqa: PLR0913
    event: EclipseEvent,
    output_path: str | Path,
    *,
    quality: str = "high",
    scene: str = "map",
    renderer: str = "cairo",
    preview: bool = False,
    disable_caching: bool = False,
) -> Path:
    """Render a scene and write the resulting MP4 to ``output_path``."""
    if importlib.util.find_spec("manim") is None:
        msg = "Manim is not installed. Install project dependencies with `uv sync`."
        raise RuntimeError(msg)

    quality_code, fps_override, resolution_override = _resolve_quality_profile(quality)
    renderer_name = renderer.lower()
    if renderer_name not in {"cairo", "opengl"}:
        msg = "renderer must be one of: cairo, opengl"
        raise ValueError(msg)

    scene_name = scene.lower()
    if scene_name not in SUPPORTED_SCENES:
        supported = ", ".join(sorted(SUPPORTED_SCENES))
        msg = f"scene must be one of: {supported}"
        raise ValueError(msg)
    if renderer_name == "opengl" and scene_name != "globe":
        msg = "renderer=opengl is currently supported only for scene=globe."
        raise ValueError(msg)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        payload_path = temp_dir / "scene_payload.json"
        script_path = temp_dir / "scene.py"
        media_dir = temp_dir / "media"
        payload = build_scene_payload(event, scene_name, preview=preview)
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        script_path.write_text(build_manim_script(payload_path, scene_name), encoding="utf-8")

        _run_manim(
            script_path,
            scene_name=scene_name,
            quality_code=quality_code,
            renderer=renderer_name,
            media_dir=media_dir,
            preview=preview,
            fps_override=fps_override,
            resolution_override=resolution_override,
            disable_caching=disable_caching,
        )

        rendered_files = list(media_dir.rglob("*.mp4"))
        if not rendered_files:
            msg = "Manim did not produce an mp4 output."
            raise RuntimeError(msg)
        newest_file = max(rendered_files, key=lambda path: path.stat().st_mtime)
        shutil.copyfile(newest_file, destination)

    return destination


def render_saros_scene(  # noqa: PLR0913
    *,
    year: int,
    name: str,
    output_path: str | Path,
    years: int = 20,
    quality: str = "high",
    renderer: str = "cairo",
    preview: bool = False,
    disable_caching: bool = False,
) -> Path:
    """Render a multi-year Saros-style path animation scene."""
    if importlib.util.find_spec("manim") is None:
        msg = "Manim is not installed. Install project dependencies with `uv sync`."
        raise RuntimeError(msg)

    quality_code, fps_override, resolution_override = _resolve_quality_profile(quality)
    renderer_name = renderer.lower()
    if renderer_name not in {"cairo", "opengl"}:
        msg = "renderer must be one of: cairo, opengl"
        raise ValueError(msg)
    if renderer_name == "opengl":
        msg = "renderer=opengl is currently not supported for render-saros."
        raise ValueError(msg)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        payload_path = temp_dir / "scene_payload.json"
        script_path = temp_dir / "scene.py"
        media_dir = temp_dir / "media"

        payload = build_saros_scene_payload(year=year, name=name, years=years, preview=preview)
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        script_path.write_text(build_manim_script(payload_path, "saros"), encoding="utf-8")

        _run_manim(
            script_path,
            scene_name="saros",
            quality_code=quality_code,
            renderer=renderer_name,
            media_dir=media_dir,
            preview=preview,
            fps_override=fps_override,
            resolution_override=resolution_override,
            disable_caching=disable_caching,
        )

        rendered_files = list(media_dir.rglob("*.mp4"))
        if not rendered_files:
            msg = "Manim did not produce an mp4 output."
            raise RuntimeError(msg)
        newest_file = max(rendered_files, key=lambda path: path.stat().st_mtime)
        shutil.copyfile(newest_file, destination)

    return destination


def _run_manim(  # noqa: PLR0913
    script_path: Path,
    *,
    scene_name: str,
    quality_code: str,
    renderer: str,
    media_dir: Path,
    preview: bool,
    fps_override: float | None,
    resolution_override: tuple[int, int] | None,
    disable_caching: bool,
) -> None:
    manim_scene_name = SUPPORTED_SCENES[scene_name]
    argv = [
        sys.executable,
        "-m",
        "manim",
        f"-q{quality_code}",
        str(script_path),
        manim_scene_name,
        "--media_dir",
        str(media_dir),
        "--renderer",
        renderer,
    ]
    if resolution_override is not None:
        width, height = resolution_override
        argv.extend(["--resolution", f"{width},{height}"])
    if fps_override is not None:
        argv.extend(["--fps", str(fps_override)])
    elif preview:
        argv.extend(["--fps", "24"])
    if disable_caching:
        argv.append("--disable_caching")
    completed = subprocess.run(argv, check=False)  # noqa: S603
    if completed.returncode != 0:
        msg = f"Manim render failed with code {completed.returncode}."
        raise RuntimeError(msg)


def _resolve_quality_profile(quality: str) -> tuple[str, float | None, tuple[int, int] | None]:
    normalized_quality = quality.lower()
    if normalized_quality in {"very-low", "vl"}:
        return "l", 12.0, (426, 240)

    quality_code = QUALITY_SHORTCUT.get(normalized_quality, normalized_quality)
    if quality_code not in {"l", "m", "h", "p", "k"}:
        msg = "quality must be one of: very-low, low, medium, high, production, 4k"
        raise ValueError(msg)
    return quality_code, None, None
