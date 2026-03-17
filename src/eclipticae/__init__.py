"""Public API for the eclipticae package."""

from eclipticae.catalog import list_global_solar_eclipses, lookup_eclipse_with_saros
from eclipticae.compute import build_timeline, compute_site_eclipse
from eclipticae.export import load_event, save_event
from eclipticae.models import EclipseEvent, TimelinePoint
from eclipticae.render import render_saros_scene, render_scene

__all__ = [
    "EclipseEvent",
    "TimelinePoint",
    "build_timeline",
    "compute_site_eclipse",
    "list_global_solar_eclipses",
    "load_event",
    "lookup_eclipse_with_saros",
    "render_saros_scene",
    "render_scene",
    "save_event",
]
