"""Build render payloads from astronomy-engine computations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astronomy import Body, GeoMoon, GeoVector, SiderealTime, Time, Vector

from ecliptica.render.constants import AU_KM, COASTLINE_ASSET_PATH, EARTH_RADIUS_AU

if TYPE_CHECKING:
    from ecliptica.models import EclipseEvent

_DEGREES_WRAP = 180.0
_MIN_LINE_POINTS = 2


@dataclass(frozen=True, slots=True)
class PayloadBuildOptions:
    """Tuning knobs used to build render payloads."""

    sample_count: int = 120
    min_step_seconds: int = 15
    coastline_stride: int = 3


_DEFAULT_PAYLOAD_OPTIONS = PayloadBuildOptions()
_PREVIEW_PAYLOAD_OPTIONS = PayloadBuildOptions(
    sample_count=48,
    min_step_seconds=30,
    coastline_stride=6,
)


def build_scene_payload(
    event: EclipseEvent,
    scene: str,
    *,
    preview: bool = False,
) -> dict[str, Any]:
    """Create the JSON payload consumed by generated Manim scene scripts."""
    options = _PREVIEW_PAYLOAD_OPTIONS if preview else _DEFAULT_PAYLOAD_OPTIONS
    payload: dict[str, Any] = {"event": event.to_dict(), "scene": scene}
    if scene in {"map", "globe"}:
        start, end = _event_bounds(event)
        payload["samples"] = _build_map_samples(start, end, options=options)
        payload["coastline_segments"] = _load_coastline_segments(
            COASTLINE_ASSET_PATH,
            stride=options.coastline_stride,
        )
    return payload


def _event_bounds(event: EclipseEvent) -> tuple[datetime, datetime]:
    start = event.partial_begin_utc or event.total_begin_utc
    end = event.partial_end_utc or event.total_end_utc
    if start is None or end is None or end <= start:
        return event.peak_utc - timedelta(hours=1), event.peak_utc + timedelta(hours=1)
    return start, end


def _build_map_samples(
    start: datetime,
    end: datetime,
    *,
    options: PayloadBuildOptions,
) -> list[dict[str, Any]]:
    duration_seconds = max((end - start).total_seconds(), 1.0)
    sample_count = max(options.sample_count, 1)
    step_seconds = max(int(duration_seconds / sample_count), options.min_step_seconds)
    samples: list[dict[str, Any]] = []
    elapsed = 0
    while elapsed < duration_seconds:
        sample_time = start + timedelta(seconds=elapsed)
        samples.append(_sample_map_state(sample_time, float(elapsed)))
        elapsed += step_seconds
    samples.append(_sample_map_state(end, float(duration_seconds)))
    return samples


def _sample_map_state(sample_time: datetime, seconds_from_start: float) -> dict[str, Any]:
    t = _to_astronomy_time(sample_time)
    sun_vec = GeoVector(Body.Sun, t, aberration=True)
    sun_lon, sun_lat = _subpoint_from_vector(sun_vec.x, sun_vec.y, sun_vec.z, t)
    shadow_lon, shadow_lat, shadow_hit, miss_km = _shadow_axis_subpoint(t, sun_vec)
    return {
        "seconds": seconds_from_start,
        "utc": _serialize_utc(sample_time),
        "sun_lon": sun_lon,
        "sun_lat": sun_lat,
        "shadow_lon": shadow_lon,
        "shadow_lat": shadow_lat,
        "shadow_hits_earth": shadow_hit,
        "shadow_miss_km": miss_km,
    }


def _shadow_axis_subpoint(time: Time, sun_vector: Vector) -> tuple[float, float, bool, float]:
    moon = GeoMoon(time)
    rx, ry, rz = moon.x, moon.y, moon.z
    sx, sy, sz = sun_vector.x, sun_vector.y, sun_vector.z

    dx, dy, dz = _normalize(rx - sx, ry - sy, rz - sz)
    b = 2.0 * (rx * dx + ry * dy + rz * dz)
    c = (rx * rx + ry * ry + rz * rz) - (EARTH_RADIUS_AU * EARTH_RADIUS_AU)
    discriminant = (b * b) - (4.0 * c)

    shadow_hits_earth = discriminant >= 0.0
    if shadow_hits_earth:
        sqrt_disc = math.sqrt(discriminant)
        roots = [(-b - sqrt_disc) / 2.0, (-b + sqrt_disc) / 2.0]
        positive_roots = [value for value in roots if value >= 0.0]
        distance = min(positive_roots) if positive_roots else min(roots, key=abs)
    else:
        distance = -((rx * dx) + (ry * dy) + (rz * dz))

    px, py, pz = rx + (distance * dx), ry + (distance * dy), rz + (distance * dz)
    lon, lat = _subpoint_from_vector(px, py, pz, time)
    radial_distance_au = math.sqrt((px * px) + (py * py) + (pz * pz))
    miss_km = max((radial_distance_au - EARTH_RADIUS_AU) * AU_KM, 0.0)
    return lon, lat, shadow_hits_earth, miss_km


def _subpoint_from_vector(x: float, y: float, z: float, time: Time) -> tuple[float, float]:
    right_ascension_deg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    declination_deg = math.degrees(math.atan2(z, math.hypot(x, y)))
    longitude = _wrap_longitude(right_ascension_deg - (SiderealTime(time) * 15.0))
    return longitude, declination_deg


def _normalize(x: float, y: float, z: float) -> tuple[float, float, float]:
    magnitude = math.sqrt((x * x) + (y * y) + (z * z))
    if magnitude == 0.0:
        return 0.0, 0.0, 0.0
    return x / magnitude, y / magnitude, z / magnitude


def _wrap_longitude(value: float) -> float:
    return ((value + _DEGREES_WRAP) % 360.0) - _DEGREES_WRAP


def _to_astronomy_time(value: datetime) -> Time:
    utc_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    utc_value = utc_value.astimezone(UTC)
    second = utc_value.second + (utc_value.microsecond / 1_000_000.0)
    return Time.Make(
        utc_value.year,
        utc_value.month,
        utc_value.day,
        utc_value.hour,
        utc_value.minute,
        second,
    )


def _serialize_utc(value: datetime) -> str:
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc_value.isoformat().replace("+00:00", "Z")


def _load_coastline_segments(path: Path, *, stride: int = 3) -> list[list[list[float]]]:
    cache_key = str(path.resolve())
    cached_segments = _load_coastline_segments_cached(cache_key, stride)
    return [[[point[0], point[1]] for point in segment] for segment in cached_segments]


@lru_cache(maxsize=8)
def _load_coastline_segments_cached(
    path_text: str,
    stride: int,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    path = Path(path_text)
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    segments: list[list[list[float]]] = []
    for feature in features:
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        if geom_type == "LineString":
            _append_segment_parts(segments, [coordinates], stride=stride)
        elif geom_type == "MultiLineString":
            _append_segment_parts(segments, coordinates, stride=stride)
    return tuple(
        tuple((float(point[0]), float(point[1])) for point in segment) for segment in segments
    )


def _append_segment_parts(
    sink: list[list[list[float]]],
    lines: list[list[list[float]]],
    *,
    stride: int = 3,
) -> None:
    for line in lines:
        active: list[list[float]] = []
        previous_lon: float | None = None
        for lon_raw, lat_raw, *_ in line:
            lon = float(lon_raw)
            lat = float(lat_raw)
            if previous_lon is not None and abs(lon - previous_lon) > _DEGREES_WRAP:
                if len(active) >= _MIN_LINE_POINTS:
                    sink.append(_downsample_segment(active, stride=stride))
                active = []
            active.append([lon, lat])
            previous_lon = lon
        if len(active) >= _MIN_LINE_POINTS:
            sink.append(_downsample_segment(active, stride=stride))


def _downsample_segment(segment: list[list[float]], *, stride: int = 3) -> list[list[float]]:
    if len(segment) <= (stride + _MIN_LINE_POINTS):
        return segment
    sampled = [segment[0]]
    sampled.extend(segment[index] for index in range(stride, len(segment) - 1, stride))
    sampled.append(segment[-1])
    return sampled
