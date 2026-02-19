"""Public API for the ecliptica package."""

from ecliptica.catalog import list_global_solar_eclipses, lookup_eclipse_with_saros
from ecliptica.compute import build_timeline, compute_site_eclipse
from ecliptica.export import load_event, save_event
from ecliptica.models import EclipseEvent, TimelinePoint
from ecliptica.render import render_saros_scene, render_scene

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
