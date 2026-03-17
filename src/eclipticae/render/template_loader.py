"""Helpers for loading render script templates from Python modules."""

from __future__ import annotations

from eclipticae.render.templates.globe_template import TEMPLATE as GLOBE_TEMPLATE
from eclipticae.render.templates.map_template import TEMPLATE as MAP_TEMPLATE
from eclipticae.render.templates.saros_template import TEMPLATE as SAROS_TEMPLATE

_TEMPLATES = {
    "map_scene.py.tmpl": MAP_TEMPLATE,
    "globe_scene.py.tmpl": GLOBE_TEMPLATE,
    "saros_scene.py.tmpl": SAROS_TEMPLATE,
}


def load_template(name: str) -> str:
    """Load one render script template by file name."""
    try:
        return _TEMPLATES[name]
    except KeyError as exc:
        msg = f"Unknown template: {name}"
        raise ValueError(msg) from exc
