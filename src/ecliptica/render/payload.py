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

from ecliptica.render.constants import (
    AU_KM,
    COASTLINE_ASSET_PATH,
    COUNTRY_BORDER_ASSET_PATH,
    EARTH_RADIUS_AU,
    EARTH_RADIUS_KM,
    LAND_ASSET_PATH,
)

if TYPE_CHECKING:
    from ecliptica.models import EclipseEvent

_DEGREES_WRAP = 180.0
_MIN_LINE_POINTS = 2
_MIN_RING_POINTS = 4
_ANTIMERIDIAN_TOLERANCE = 1e-9
_MIN_HEADING_SAMPLE_COUNT = 2
_SUN_RADIUS_KM = 695700.0
_MOON_RADIUS_KM = 1737.4
_MAX_TRIG_RATIO = 1.0
_MIN_AXIS_DISTANCE_KM = 1.0
_HEADING_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class PayloadBuildOptions:
    """Tuning knobs used to build render payloads."""

    sample_count: int = 120
    min_step_seconds: int = 15
    coastline_stride: int = 3
    land_stride: int = 2


_DEFAULT_PAYLOAD_OPTIONS = PayloadBuildOptions()
_PREVIEW_PAYLOAD_OPTIONS = PayloadBuildOptions(
    sample_count=48,
    min_step_seconds=30,
    coastline_stride=6,
    land_stride=4,
)


def build_scene_payload(
    event: EclipseEvent,
    scene: str,
    *,
    preview: bool = False,
    style: str = "classic",
) -> dict[str, Any]:
    """Create the JSON payload consumed by generated Manim scene scripts."""
    options = _PREVIEW_PAYLOAD_OPTIONS if preview else _DEFAULT_PAYLOAD_OPTIONS
    payload: dict[str, Any] = {"event": event.to_dict(), "scene": scene, "style": style}
    if scene in {"map", "globe"}:
        start, end = _event_bounds(event)
        payload["samples"] = _build_map_samples(start, end, options=options)
        payload.update(load_cartography(preview=preview))
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
    _attach_path_products(samples)
    return samples


def build_shadow_samples_between(
    start: datetime,
    end: datetime,
    *,
    preview: bool = False,
) -> list[dict[str, Any]]:
    """Build shadow-axis samples for an arbitrary UTC interval."""
    options = _PREVIEW_PAYLOAD_OPTIONS if preview else _DEFAULT_PAYLOAD_OPTIONS
    return _build_map_samples(start, end, options=options)


def load_cartography(*, preview: bool = False) -> dict[str, Any]:
    """Load coastlines, country borders, and land polygon assets."""
    options = _PREVIEW_PAYLOAD_OPTIONS if preview else _DEFAULT_PAYLOAD_OPTIONS
    return {
        "coastline_segments": _load_coastline_segments(
            COASTLINE_ASSET_PATH,
            stride=options.coastline_stride,
        ),
        "country_border_segments": _load_coastline_segments(
            COUNTRY_BORDER_ASSET_PATH,
            stride=options.coastline_stride,
        ),
        "land_polygons": _load_land_polygons(
            LAND_ASSET_PATH,
            stride=options.land_stride,
        ),
    }


def _sample_map_state(sample_time: datetime, seconds_from_start: float) -> dict[str, Any]:
    t = _to_astronomy_time(sample_time)
    sun_vec = GeoVector(Body.Sun, t, aberration=True)
    moon_vec = GeoMoon(t)
    sun_lon, sun_lat = _subpoint_from_vector(sun_vec.x, sun_vec.y, sun_vec.z, t)
    (
        shadow_lon,
        shadow_lat,
        shadow_hit,
        miss_km,
        penumbra_radius_km,
        core_radius_km,
        core_kind,
    ) = _shadow_axis_subpoint(
        t,
        sun_vec,
        moon_vec,
    )
    return {
        "seconds": seconds_from_start,
        "utc": _serialize_utc(sample_time),
        "sun_lon": sun_lon,
        "sun_lat": sun_lat,
        "shadow_lon": shadow_lon,
        "shadow_lat": shadow_lat,
        "shadow_hits_earth": shadow_hit,
        "shadow_miss_km": miss_km,
        "penumbra_radius_km": penumbra_radius_km,
        "core_radius_km": core_radius_km,
        "core_kind": core_kind,
    }


def _attach_path_products(samples: list[dict[str, Any]]) -> None:
    if len(samples) < _MIN_HEADING_SAMPLE_COUNT:
        return
    for index, sample in enumerate(samples):
        heading_deg = _sample_heading_deg(samples, index)
        center_lon = float(sample["shadow_lon"])
        center_lat = float(sample["shadow_lat"])
        penumbra_radius_km = max(float(sample["penumbra_radius_km"]), 0.0)
        core_radius_km = max(float(sample["core_radius_km"]), 0.0)
        penumbra_north = _destination_point(
            center_lat,
            center_lon,
            heading_deg + 90.0,
            penumbra_radius_km,
        )
        penumbra_south = _destination_point(
            center_lat,
            center_lon,
            heading_deg - 90.0,
            penumbra_radius_km,
        )
        core_north = _destination_point(
            center_lat,
            center_lon,
            heading_deg + 90.0,
            core_radius_km,
        )
        core_south = _destination_point(
            center_lat,
            center_lon,
            heading_deg - 90.0,
            core_radius_km,
        )
        sample["path_heading_deg"] = heading_deg
        sample["penumbra_north_lon"] = penumbra_north[1]
        sample["penumbra_north_lat"] = penumbra_north[0]
        sample["penumbra_south_lon"] = penumbra_south[1]
        sample["penumbra_south_lat"] = penumbra_south[0]
        sample["core_north_lon"] = core_north[1]
        sample["core_north_lat"] = core_north[0]
        sample["core_south_lon"] = core_south[1]
        sample["core_south_lat"] = core_south[0]


def _sample_heading_deg(samples: list[dict[str, Any]], index: int) -> float:
    if index <= 0:
        start = samples[0]
        end = samples[1]
    elif index >= len(samples) - 1:
        start = samples[-2]
        end = samples[-1]
    else:
        start = samples[index - 1]
        end = samples[index + 1]
    heading = _initial_bearing_deg(
        float(start["shadow_lat"]),
        float(start["shadow_lon"]),
        float(end["shadow_lat"]),
        float(end["shadow_lon"]),
    )
    if heading is None:
        return 90.0
    return heading


def _initial_bearing_deg(
    start_lat_deg: float,
    start_lon_deg: float,
    end_lat_deg: float,
    end_lon_deg: float,
) -> float | None:
    start_lat = math.radians(start_lat_deg)
    start_lon = math.radians(start_lon_deg)
    end_lat = math.radians(end_lat_deg)
    end_lon = math.radians(end_lon_deg)
    delta_lon = end_lon - start_lon
    y_component = math.sin(delta_lon) * math.cos(end_lat)
    x_component = (math.cos(start_lat) * math.sin(end_lat)) - (
        math.sin(start_lat) * math.cos(end_lat) * math.cos(delta_lon)
    )
    if abs(x_component) < _HEADING_EPSILON and abs(y_component) < _HEADING_EPSILON:
        return None
    bearing_deg = math.degrees(math.atan2(y_component, x_component))
    return (bearing_deg + 360.0) % 360.0


def _destination_point(
    start_lat_deg: float,
    start_lon_deg: float,
    bearing_deg: float,
    distance_km: float,
) -> tuple[float, float]:
    if distance_km <= 0.0:
        return start_lat_deg, _wrap_longitude(start_lon_deg)

    angular_distance = distance_km / EARTH_RADIUS_KM
    start_lat = math.radians(start_lat_deg)
    start_lon = math.radians(start_lon_deg)
    bearing = math.radians(bearing_deg)

    end_lat = math.asin(
        (math.sin(start_lat) * math.cos(angular_distance))
        + (math.cos(start_lat) * math.sin(angular_distance) * math.cos(bearing)),
    )
    end_lon = start_lon + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(start_lat),
        math.cos(angular_distance) - (math.sin(start_lat) * math.sin(end_lat)),
    )
    lat_deg = math.degrees(end_lat)
    lon_deg = _wrap_longitude(math.degrees(end_lon))
    return lat_deg, lon_deg


def _shadow_axis_subpoint(
    time: Time,
    sun_vector: Vector,
    moon_vector: Vector,
) -> tuple[float, float, bool, float, float, float, str]:
    rx, ry, rz = moon_vector.x, moon_vector.y, moon_vector.z
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
    penumbra_radius_km, core_radius_km, core_kind = _physical_shadow_region_radii_km(
        sun_vector=sun_vector,
        axis_point_au=(px, py, pz),
        axis_distance_au=distance,
        shadow_hits_earth=shadow_hits_earth,
    )
    return (
        lon,
        lat,
        shadow_hits_earth,
        miss_km,
        penumbra_radius_km,
        core_radius_km,
        core_kind,
    )


def _physical_shadow_region_radii_km(
    *,
    sun_vector: Vector,
    axis_point_au: tuple[float, float, float],
    axis_distance_au: float,
    shadow_hits_earth: bool,
) -> tuple[float, float, str]:
    axis_distance_km = max(abs(axis_distance_au) * AU_KM, _MIN_AXIS_DISTANCE_KM)
    sx, sy, sz = sun_vector.x, sun_vector.y, sun_vector.z
    px, py, pz = axis_point_au
    sun_distance_km = (
        math.sqrt(
            ((sx - px) * (sx - px)) + ((sy - py) * (sy - py)) + ((sz - pz) * (sz - pz)),
        )
        * AU_KM
    )
    if sun_distance_km <= _SUN_RADIUS_KM:
        return 0.0, 0.0, "umbra"

    moon_ratio = min(_MOON_RADIUS_KM / axis_distance_km, _MAX_TRIG_RATIO)
    sun_ratio = min(_SUN_RADIUS_KM / sun_distance_km, _MAX_TRIG_RATIO)
    moon_angular_radius = math.asin(moon_ratio)
    sun_angular_radius = math.asin(sun_ratio)
    penumbra_half_angle = moon_angular_radius + sun_angular_radius
    core_half_angle = abs(moon_angular_radius - sun_angular_radius)

    penumbra_radius_km = axis_distance_km * math.tan(penumbra_half_angle)
    core_radius_km = axis_distance_km * math.tan(core_half_angle)
    core_kind = (
        "umbra" if shadow_hits_earth and moon_angular_radius >= sun_angular_radius else "antumbra"
    )
    return max(penumbra_radius_km, 0.0), max(core_radius_km, 0.0), core_kind


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


def _load_land_polygons(path: Path, *, stride: int = 2) -> list[list[list[float]]]:
    cache_key = str(path.resolve())
    cached_polygons = _load_land_polygons_cached(cache_key, stride)
    return [[[point[0], point[1]] for point in polygon] for polygon in cached_polygons]


@lru_cache(maxsize=8)
def _load_land_polygons_cached(
    path_text: str,
    stride: int,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    path = Path(path_text)
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    polygons: list[list[list[float]]] = []
    for feature in features:
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        if geom_type == "Polygon":
            _append_polygon_parts(polygons, coordinates, stride=stride)
        elif geom_type == "MultiPolygon":
            for polygon in coordinates:
                _append_polygon_parts(polygons, polygon, stride=stride)
    return tuple(
        tuple((float(point[0]), float(point[1])) for point in polygon) for polygon in polygons
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
            lon = _normalize_antimeridian_lon(float(lon_raw))
            lat = float(lat_raw)
            if previous_lon is not None and abs(lon - previous_lon) > _DEGREES_WRAP:
                if len(active) >= _MIN_LINE_POINTS:
                    sink.append(_downsample_segment(active, stride=stride))
                active = []
            active.append([lon, lat])
            previous_lon = lon
        if len(active) >= _MIN_LINE_POINTS:
            sink.append(_downsample_segment(active, stride=stride))


def _append_polygon_parts(
    sink: list[list[list[float]]],
    rings: list[list[list[float]]],
    *,
    stride: int = 2,
) -> None:
    if not rings:
        return
    outer_ring = rings[0]
    if len(outer_ring) < _MIN_RING_POINTS:
        return
    sampled_ring = _downsample_segment(
        [
            [_normalize_antimeridian_lon(float(lon_raw)), float(lat_raw)]
            for lon_raw, lat_raw, *_ in outer_ring
        ],
        stride=stride,
    )
    if len(sampled_ring) < _MIN_RING_POINTS:
        return
    if sampled_ring[0] != sampled_ring[-1]:
        sampled_ring.append(sampled_ring[0])
    sink.append(sampled_ring)


def _downsample_segment(segment: list[list[float]], *, stride: int = 3) -> list[list[float]]:
    if len(segment) <= (stride + _MIN_LINE_POINTS):
        return segment
    sampled = [segment[0]]
    sampled.extend(segment[index] for index in range(stride, len(segment) - 1, stride))
    sampled.append(segment[-1])
    return sampled


def _normalize_antimeridian_lon(lon: float) -> float:
    if abs(abs(lon) - _DEGREES_WRAP) < _ANTIMERIDIAN_TOLERANCE:
        return math.copysign(_DEGREES_WRAP, lon)
    return lon
