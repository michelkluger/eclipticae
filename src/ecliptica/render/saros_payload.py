"""Payload generation for the Saros-style multi-year path animation scene."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ecliptica.catalog import list_global_solar_eclipses, lookup_eclipse_with_saros
from ecliptica.render.payload import build_shadow_samples_between, load_cartography

_SAROS_PERIOD_DAYS = 6585.321667
_SECONDS_PER_DAY = 86400.0
_DEFAULT_YEARS = 20
_WINDOW_HOURS = 2.0


def build_saros_scene_payload(
    *,
    year: int,
    name: str,
    years: int = _DEFAULT_YEARS,
    preview: bool = False,
) -> dict[str, Any]:
    """Build a multi-year eclipse path payload with Saros context metadata."""
    if years < 1:
        msg = "years must be at least 1"
        raise ValueError(msg)

    lookup = lookup_eclipse_with_saros(year=year, name=name, saros_span=3, window_days=60)
    anchor = lookup["match"]
    anchor_peak = _parse_utc(anchor["peak_utc"])
    saros_period_seconds = _SAROS_PERIOD_DAYS * _SECONDS_PER_DAY

    events = []
    for current_year in range(year, year + years):
        events.extend(list_global_solar_eclipses(current_year))
    events.sort(key=lambda item: item.peak_utc)

    scene_events: list[dict[str, Any]] = []
    for event in events:
        start = event.peak_utc - timedelta(hours=_WINDOW_HOURS)
        end = event.peak_utc + timedelta(hours=_WINDOW_HOURS)
        samples = build_shadow_samples_between(start, end, preview=preview)
        path_products = _build_path_products(samples)

        delta_seconds = (event.peak_utc - anchor_peak).total_seconds()
        nearest_offset = round(delta_seconds / saros_period_seconds)
        phase_days = (delta_seconds - (nearest_offset * saros_period_seconds)) / _SECONDS_PER_DAY

        scene_events.append(
            {
                "eclipse_id": event.eclipse_id,
                "name": event.name,
                "event_kind": event.event_kind,
                "peak_utc": event.peak_utc.isoformat().replace("+00:00", "Z"),
                "latitude": event.latitude,
                "longitude": event.longitude,
                "obscuration": event.obscuration,
                "distance_km": event.distance_km,
                "saros_offset": nearest_offset,
                "saros_phase_days": round(phase_days, 4),
                "path": path_products,
            },
        )

    payload: dict[str, Any] = {
        "scene": "saros",
        "query": {"year": year, "name": name, "years": years},
        "anchor": anchor,
        "saros_period_days": _SAROS_PERIOD_DAYS,
        "saros_cycle": lookup["saros_cycle"],
        "events": scene_events,
    }
    payload.update(load_cartography(preview=preview))
    return payload


def _build_path_products(samples: list[dict[str, Any]]) -> dict[str, list[list[float]]]:
    return {
        "centerline": _points_from_samples(samples, "shadow_lon", "shadow_lat"),
        "penumbra_north": _points_from_samples(samples, "penumbra_north_lon", "penumbra_north_lat"),
        "penumbra_south": _points_from_samples(samples, "penumbra_south_lon", "penumbra_south_lat"),
        "core_north": _points_from_samples(samples, "core_north_lon", "core_north_lat"),
        "core_south": _points_from_samples(samples, "core_south_lon", "core_south_lat"),
    }


def _points_from_samples(
    samples: list[dict[str, Any]],
    lon_key: str,
    lat_key: str,
) -> list[list[float]]:
    return [[float(sample[lon_key]), float(sample[lat_key])] for sample in samples]


def _parse_utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw)
