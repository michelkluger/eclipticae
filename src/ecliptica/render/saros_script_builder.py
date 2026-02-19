"""Build the saros scene script source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ecliptica.render.template_loader import load_template

if TYPE_CHECKING:
    from pathlib import Path

_TEMPLATE_NAME = "saros_scene.py.tmpl"


def build_saros_script(payload_path: Path) -> str:
    """Build the saros scene script."""
    template = load_template(_TEMPLATE_NAME)
    return template.replace("__PAYLOAD_PATH__", payload_path.as_posix())
