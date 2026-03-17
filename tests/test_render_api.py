"""Tests for render API runtime wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from eclipticae.models import EclipseEvent
from eclipticae.render.api import (
    _resolve_quality_profile,
    _run_manim,
    render_saros_scene,
    render_scene,
)


def test_run_manim_respects_preview_and_caching_flags() -> None:
    """Manim argv should include preview fps and optional cache disabling."""
    captured_argv: list[str] = []

    def fake_subprocess_run(argv: list[str], *, check: bool) -> SimpleNamespace:
        del check
        captured_argv.extend(argv)
        return SimpleNamespace(returncode=0)

    with patch("eclipticae.render.api.subprocess.run", side_effect=fake_subprocess_run):
        _run_manim(
            Path("dummy_scene.py"),
            scene_name="map",
            quality_code="l",
            renderer="opengl",
            media_dir=Path("dummy_media"),
            preview=True,
            fps_override=None,
            resolution_override=None,
            disable_caching=True,
        )

    if "-m" not in captured_argv or "manim" not in captured_argv:
        raise AssertionError
    if "--renderer" not in captured_argv:
        raise AssertionError
    if "opengl" not in captured_argv:
        raise AssertionError
    if "--fps" not in captured_argv:
        raise AssertionError
    if "24" not in captured_argv:
        raise AssertionError
    if "--disable_caching" not in captured_argv:
        raise AssertionError


def test_run_manim_keeps_caching_enabled_by_default() -> None:
    """Manim argv should omit disable flag when caching is enabled."""
    captured_argv: list[str] = []

    def fake_subprocess_run(argv: list[str], *, check: bool) -> SimpleNamespace:
        del check
        captured_argv.extend(argv)
        return SimpleNamespace(returncode=0)

    with patch("eclipticae.render.api.subprocess.run", side_effect=fake_subprocess_run):
        _run_manim(
            Path("dummy_scene.py"),
            scene_name="globe",
            quality_code="m",
            renderer="cairo",
            media_dir=Path("dummy_media"),
            preview=False,
            fps_override=None,
            resolution_override=None,
            disable_caching=False,
        )

    if "--disable_caching" in captured_argv:
        raise AssertionError


def test_run_manim_supports_saros_scene_name() -> None:
    """Manim argv should include Saros scene class for saros renders."""
    captured_argv: list[str] = []

    def fake_subprocess_run(argv: list[str], *, check: bool) -> SimpleNamespace:
        del check
        captured_argv.extend(argv)
        return SimpleNamespace(returncode=0)

    with patch("eclipticae.render.api.subprocess.run", side_effect=fake_subprocess_run):
        _run_manim(
            Path("dummy_scene.py"),
            scene_name="saros",
            quality_code="l",
            renderer="cairo",
            media_dir=Path("dummy_media"),
            preview=False,
            fps_override=None,
            resolution_override=None,
            disable_caching=False,
        )

    if "SarosMapScene" not in captured_argv:
        raise AssertionError


def test_run_manim_raises_on_nonzero_exit() -> None:
    """Non-zero manim exit codes should surface as RuntimeError."""

    def fake_subprocess_run(argv: list[str], *, check: bool) -> SimpleNamespace:
        del argv, check
        return SimpleNamespace(returncode=7)

    with patch("eclipticae.render.api.subprocess.run", side_effect=fake_subprocess_run):
        try:
            _run_manim(
                Path("dummy_scene.py"),
                scene_name="map",
                quality_code="l",
                renderer="cairo",
                media_dir=Path("dummy_media"),
                preview=False,
                fps_override=None,
                resolution_override=None,
                disable_caching=False,
            )
        except RuntimeError:
            return

    raise AssertionError


def test_render_scene_rejects_opengl_for_map() -> None:
    """Map scene should reject OpenGL with a clear early error."""
    event = _sample_event()
    with patch("eclipticae.render.api.importlib.util.find_spec", return_value=object()):
        try:
            render_scene(
                event,
                Path("out.mp4"),
                scene="map",
                renderer="opengl",
                preview=True,
            )
        except ValueError as exc:
            if "renderer=opengl" not in str(exc):
                raise AssertionError from exc
            return
    raise AssertionError


def test_render_saros_rejects_opengl() -> None:
    """Saros scene should reject OpenGL with a clear early error."""
    with patch("eclipticae.render.api.importlib.util.find_spec", return_value=object()):
        try:
            render_saros_scene(
                year=2026,
                name="total",
                output_path=Path("saros.mp4"),
                renderer="opengl",
                preview=True,
            )
        except ValueError as exc:
            if "renderer=opengl" not in str(exc):
                raise AssertionError from exc
            return
    raise AssertionError


def test_resolve_quality_profile_supports_very_low() -> None:
    """Very-low quality should map to low flag with extra downscale overrides."""
    expected_preview_fps = 12.0
    quality_code, fps_override, resolution_override = _resolve_quality_profile("very-low")
    if quality_code != "l":
        raise AssertionError
    if fps_override != expected_preview_fps:
        raise AssertionError
    if resolution_override != (426, 240):
        raise AssertionError


def _sample_event() -> EclipseEvent:
    return EclipseEvent(
        latitude=40.4168,
        longitude=-3.7038,
        elevation_m=667.0,
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
