"""Tests for generated Manim script source builders."""

from __future__ import annotations

import ast
from pathlib import Path

from ecliptica.render.constants import SUPPORTED_SCENES
from ecliptica.render.script_builders import build_manim_script
from ecliptica.render.template_loader import load_template

_PAYLOAD_PATH = Path("scene_payload.json")


def test_build_manim_script_generates_valid_python_for_supported_scenes() -> None:
    """All supported scenes should generate parseable Python source."""
    for scene_name, scene_class_name in SUPPORTED_SCENES.items():
        script = build_manim_script(_PAYLOAD_PATH, scene_name)

        if "__PAYLOAD_PATH__" in script:
            raise AssertionError
        if _PAYLOAD_PATH.as_posix() not in script:
            raise AssertionError
        if scene_class_name not in script:
            raise AssertionError

        try:
            ast.parse(script)
        except SyntaxError as exc:
            raise AssertionError from exc


def test_build_manim_script_rejects_unsupported_scene() -> None:
    """Unsupported scene names should raise ValueError."""
    try:
        build_manim_script(_PAYLOAD_PATH, "unknown-scene")
    except ValueError as exc:
        if "Unsupported scene" not in str(exc):
            raise AssertionError from exc
        return
    raise AssertionError


def test_load_template_rejects_unknown_name() -> None:
    """Template loader should raise ValueError for unknown template names."""
    try:
        load_template("unknown.py.tmpl")
    except ValueError as exc:
        if "Unknown template" not in str(exc):
            raise AssertionError from exc
        return
    raise AssertionError
