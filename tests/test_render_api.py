"""Tests for render API runtime wiring."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from ecliptica.render.api import _run_manim


def test_run_manim_respects_preview_and_caching_flags() -> None:
    """Manim argv should include preview fps and optional cache disabling."""
    captured_argv: list[str] = []

    def fake_run_module(module_name: str, run_name: str) -> None:
        del module_name, run_name
        captured_argv.extend(sys.argv)
        raise SystemExit(0)

    with patch("ecliptica.render.api.runpy.run_module", side_effect=fake_run_module):
        _run_manim(
            Path("dummy_scene.py"),
            scene_name="map",
            quality_code="l",
            media_dir=Path("dummy_media"),
            preview=True,
            disable_caching=True,
        )

    if "--fps" not in captured_argv:
        raise AssertionError
    if "24" not in captured_argv:
        raise AssertionError
    if "--disable_caching" not in captured_argv:
        raise AssertionError


def test_run_manim_keeps_caching_enabled_by_default() -> None:
    """Manim argv should omit disable flag when caching is enabled."""
    captured_argv: list[str] = []

    def fake_run_module(module_name: str, run_name: str) -> None:
        del module_name, run_name
        captured_argv.extend(sys.argv)
        raise SystemExit(0)

    with patch("ecliptica.render.api.runpy.run_module", side_effect=fake_run_module):
        _run_manim(
            Path("dummy_scene.py"),
            scene_name="globe",
            quality_code="m",
            media_dir=Path("dummy_media"),
            preview=False,
            disable_caching=False,
        )

    if "--disable_caching" in captured_argv:
        raise AssertionError
