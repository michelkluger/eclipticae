"""Runtime rendering API that orchestrates payload and scene generation."""

from __future__ import annotations

import importlib.util
import json
import runpy
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ecliptica.render.constants import QUALITY_SHORTCUT, SUPPORTED_SCENES
from ecliptica.render.payload import build_scene_payload
from ecliptica.render.script_builders import build_manim_script

if TYPE_CHECKING:
    from ecliptica.models import EclipseEvent


def render_scene(  # noqa: PLR0913
    event: EclipseEvent,
    output_path: str | Path,
    *,
    quality: str = "high",
    scene: str = "map",
    preview: bool = False,
    disable_caching: bool = False,
) -> Path:
    """Render a scene and write the resulting MP4 to ``output_path``."""
    if importlib.util.find_spec("manim") is None:
        msg = "Manim is not installed. Install visualization extras with `uv sync --extra viz`."
        raise RuntimeError(msg)

    quality_code = QUALITY_SHORTCUT.get(quality.lower(), quality.lower())
    if quality_code not in {"l", "m", "h", "p", "k"}:
        msg = "quality must be one of: low, medium, high, production, 4k"
        raise ValueError(msg)

    scene_name = scene.lower()
    if scene_name not in SUPPORTED_SCENES:
        supported = ", ".join(sorted(SUPPORTED_SCENES))
        msg = f"scene must be one of: {supported}"
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
            media_dir=media_dir,
            preview=preview,
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
    media_dir: Path,
    preview: bool,
    disable_caching: bool,
) -> None:
    manim_scene_name = SUPPORTED_SCENES[scene_name]
    argv = [
        "manim",
        f"-q{quality_code}",
        str(script_path),
        manim_scene_name,
        "--media_dir",
        str(media_dir),
    ]
    if preview:
        argv.extend(["--fps", "24"])
    if disable_caching:
        argv.append("--disable_caching")

    original_argv = sys.argv
    sys.argv = argv
    try:
        runpy.run_module("manim", run_name="__main__")
    except SystemExit as exc:
        exit_code = _extract_exit_code(exc.code)
        if exit_code != 0:
            msg = f"Manim render failed with code {exit_code}."
            raise RuntimeError(msg) from exc
    finally:
        sys.argv = original_argv


def _extract_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1
