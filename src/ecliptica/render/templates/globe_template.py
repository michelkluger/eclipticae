# ruff: noqa: Q001
"""Render scene template source."""

from __future__ import annotations

TEMPLATE = '''from __future__ import annotations

import bisect
import json
import math

from manim import (
    DEGREES,
    ORANGE,
    UP,
    WHITE,
    Create,
    Dot3D,
    FadeIn,
    Line3D,
    Polygon,
    Sphere,
    ThreeDScene,
    VGroup,
    VMobject,
    ValueTracker,
    always_redraw,
    linear,
)


class GlobeShadowScene(ThreeDScene):
    def construct(self):
        with open("__PAYLOAD_PATH__", "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)

        event = payload["event"]
        samples = payload.get("samples", [])
        coastlines = payload.get("coastline_segments", [])
        country_borders = payload.get("country_border_segments", [])
        land_polygons = payload.get("land_polygons", [])
        if not samples:
            raise RuntimeError("Globe scene requires precomputed samples.")

        self.camera.background_color = "#060e1b"
        self.set_camera_orientation(phi=66 * DEGREES, theta=-118 * DEGREES, zoom=1.05)
        self.begin_ambient_camera_rotation(rate=0.07)
        event_color = _event_color(event.get("event_kind", "unknown"))

        radius = 2.25
        duration = max(samples[-1]["seconds"], 1.0)
        seconds_axis = [sample["seconds"] for sample in samples]

        def sample_at(seconds: float):
            if seconds <= seconds_axis[0]:
                return samples[0]
            if seconds >= seconds_axis[-1]:
                return samples[-1]
            right_index = bisect.bisect_right(seconds_axis, seconds)
            left = samples[right_index - 1]
            right = samples[right_index]
            span = max(right["seconds"] - left["seconds"], 1e-9)
            alpha = (seconds - left["seconds"]) / span
            return {
                "sun_lon": _lerp_longitude(left["sun_lon"], right["sun_lon"], alpha),
                "sun_lat": _lerp(left["sun_lat"], right["sun_lat"], alpha),
                "shadow_lon": _lerp_longitude(left["shadow_lon"], right["shadow_lon"], alpha),
                "shadow_lat": _lerp(left["shadow_lat"], right["shadow_lat"], alpha),
                "penumbra_radius_km": _lerp(
                    left["penumbra_radius_km"],
                    right["penumbra_radius_km"],
                    alpha,
                ),
                "penumbra_north_lon": _lerp_longitude(
                    left["penumbra_north_lon"],
                    right["penumbra_north_lon"],
                    alpha,
                ),
                "penumbra_north_lat": _lerp(
                    left["penumbra_north_lat"],
                    right["penumbra_north_lat"],
                    alpha,
                ),
                "penumbra_south_lon": _lerp_longitude(
                    left["penumbra_south_lon"],
                    right["penumbra_south_lon"],
                    alpha,
                ),
                "penumbra_south_lat": _lerp(
                    left["penumbra_south_lat"],
                    right["penumbra_south_lat"],
                    alpha,
                ),
                "core_radius_km": _lerp(left["core_radius_km"], right["core_radius_km"], alpha),
                "core_north_lon": _lerp_longitude(
                    left["core_north_lon"],
                    right["core_north_lon"],
                    alpha,
                ),
                "core_north_lat": _lerp(left["core_north_lat"], right["core_north_lat"], alpha),
                "core_south_lon": _lerp_longitude(
                    left["core_south_lon"],
                    right["core_south_lon"],
                    alpha,
                ),
                "core_south_lat": _lerp(left["core_south_lat"], right["core_south_lat"], alpha),
                "core_kind": left["core_kind"] if alpha < 0.5 else right["core_kind"],
                "shadow_hits_earth": (
                    left["shadow_hits_earth"]
                    if alpha < 0.5
                    else right["shadow_hits_earth"]
                ),
            }

        earth = Sphere(
            radius=radius,
            resolution=(52, 104),
            fill_color="#0f3f68",
            fill_opacity=1.0,
            stroke_width=0.0,
            checkerboard_colors=["#0f3f68", "#0f3f68"],
        )
        land_mesh = _build_globe_land(land_polygons, radius + 0.004)
        coastline_mesh = _build_globe_coastlines(coastlines, radius + 0.005)
        country_border_mesh = _build_globe_country_borders(country_borders, radius + 0.006)
        centerline_track = _build_globe_track(
            samples,
            "shadow_lon",
            "shadow_lat",
            radius + 0.028,
            color=event_color,
            stroke_width=2.2,
            stroke_opacity=0.9,
        )
        penumbra_north_track = _build_globe_track(
            samples,
            "penumbra_north_lon",
            "penumbra_north_lat",
            radius + 0.022,
            color="#d9e5f4",
            stroke_width=1.05,
            stroke_opacity=0.58,
        )
        penumbra_south_track = _build_globe_track(
            samples,
            "penumbra_south_lon",
            "penumbra_south_lat",
            radius + 0.022,
            color="#d9e5f4",
            stroke_width=1.05,
            stroke_opacity=0.58,
        )
        core_north_track = _build_globe_track(
            samples,
            "core_north_lon",
            "core_north_lat",
            radius + 0.025,
            color="#ffffff",
            stroke_width=1.28,
            stroke_opacity=0.72,
        )
        core_south_track = _build_globe_track(
            samples,
            "core_south_lon",
            "core_south_lat",
            radius + 0.025,
            color="#ffffff",
            stroke_width=1.28,
            stroke_opacity=0.72,
        )
        tracker = ValueTracker(0.0)

        sun_dot = always_redraw(
            lambda: Dot3D(
                _lon_lat_to_xyz(
                    sample_at(tracker.get_value())["sun_lon"],
                    sample_at(tracker.get_value())["sun_lat"],
                    radius + 0.12,
                ),
                radius=0.055,
                color=ORANGE,
            )
        )
        shadow_dot = always_redraw(
            lambda: Dot3D(
                _lon_lat_to_xyz(
                    sample_at(tracker.get_value())["shadow_lon"],
                    sample_at(tracker.get_value())["shadow_lat"],
                    radius + 0.06,
                ),
                radius=0.055,
                color=WHITE,
            )
        )
        observer_dot = Dot3D(
            _lon_lat_to_xyz(event["longitude"], event["latitude"], radius + 0.05),
            radius=0.052,
            color="#ff4fb3",
        )
        cone = always_redraw(lambda: _build_shadow_cone(sample_at(tracker.get_value()), radius))
        self.play(
            Create(earth),
            FadeIn(land_mesh),
            FadeIn(coastline_mesh),
            FadeIn(country_border_mesh),
            Create(penumbra_north_track),
            Create(penumbra_south_track),
            Create(core_north_track),
            Create(core_south_track),
            Create(centerline_track),
        )
        self.play(FadeIn(observer_dot), FadeIn(sun_dot), FadeIn(shadow_dot), FadeIn(cone))
        self.play(tracker.animate.set_value(duration), run_time=12.0, rate_func=linear)
        self.wait(0.8)
        self.stop_ambient_camera_rotation()


def _build_globe_land(polygons, radius: float):
    group = VGroup()
    for polygon in polygons[:350]:
        if len(polygon) < 4:
            continue
        points = [_lon_lat_to_xyz(lon, lat, radius) for lon, lat in polygon]
        if len(points) < 2:
            continue
        curve = VMobject(stroke_color="#5b8f61", stroke_width=1.2, stroke_opacity=0.52)
        curve.set_points_as_corners(points)
        curve.set_shade_in_3d(True)
        group.add(curve)
    return group


def _build_globe_coastlines(segments, radius: float):
    group = VGroup()
    for segment in segments[:450]:
        if len(segment) < 2:
            continue
        points = [_lon_lat_to_xyz(lon, lat, radius) for lon, lat in segment]
        curve = VMobject(stroke_color="#deeadf", stroke_width=0.85, stroke_opacity=0.88)
        curve.set_points_as_corners(points)
        curve.set_shade_in_3d(True)
        group.add(curve)
    return group


def _build_globe_country_borders(segments, radius: float):
    group = VGroup()
    for segment in segments[:520]:
        if len(segment) < 2:
            continue
        points = [_lon_lat_to_xyz(lon, lat, radius) for lon, lat in segment]
        curve = VMobject(stroke_color="#adc7db", stroke_width=0.52, stroke_opacity=0.48)
        curve.set_points_as_corners(points)
        curve.set_shade_in_3d(True)
        group.add(curve)
    return group


def _build_globe_track(
    samples,
    lon_key,
    lat_key,
    radius: float,
    *,
    color: str,
    stroke_width: float,
    stroke_opacity: float,
):
    group = VGroup()
    active_points = []
    previous_lon = None
    for sample in samples:
        lon = float(sample[lon_key])
        lat = float(sample[lat_key])
        if previous_lon is not None and abs(lon - previous_lon) > 170.0:
            if len(active_points) >= 2:
                curve = VMobject(
                    stroke_color=color,
                    stroke_width=stroke_width,
                    stroke_opacity=stroke_opacity,
                )
                curve.set_points_as_corners(active_points)
                curve.set_shade_in_3d(True)
                group.add(curve)
            active_points = []
        active_points.append(_lon_lat_to_xyz(lon, lat, radius))
        previous_lon = lon
    if len(active_points) >= 2:
        curve = VMobject(
            stroke_color=color,
            stroke_width=stroke_width,
            stroke_opacity=stroke_opacity,
        )
        curve.set_points_as_corners(active_points)
        curve.set_shade_in_3d(True)
        group.add(curve)
    return group


def _build_shadow_cone(sample, radius: float):
    shadow_center = _lon_lat_to_xyz(sample["shadow_lon"], sample["shadow_lat"], radius + 0.06)
    sun_source = _lon_lat_to_xyz(sample["sun_lon"], sample["sun_lat"], radius + 4.1)
    km_to_units = radius / 6371.0
    penumbra_radius = max(float(sample["penumbra_radius_km"]) * km_to_units, 0.08)
    core_radius = max(float(sample["core_radius_km"]) * km_to_units, 0.03)
    basis_a, basis_b = _tangent_basis(_normalize(shadow_center))

    group = VGroup()
    group.add(Line3D(sun_source, shadow_center, color="#ffe6b0", thickness=0.016))
    group.add(
        _build_cone_shell(
            sun_source,
            shadow_center,
            basis_a,
            basis_b,
            penumbra_radius,
            shell_color="#f5ead0",
            shell_opacity=0.2,
            rim_color="#f6f2e3",
            rim_width=1.0,
        )
    )
    core_kind = sample.get("core_kind", "umbra")
    core_fill = "#d9edff" if core_kind == "umbra" else "#fff1cc"
    group.add(
        _build_cone_shell(
            sun_source,
            shadow_center,
            basis_a,
            basis_b,
            core_radius,
            shell_color=core_fill,
            shell_opacity=0.24,
            rim_color="#ffffff",
            rim_width=1.15,
        )
    )
    return group


def _build_cone_shell(
    source,
    center,
    basis_a,
    basis_b,
    radius: float,
    *,
    shell_color: str,
    shell_opacity: float,
    rim_color: str,
    rim_width: float,
):
    ring = _build_ring(center, basis_a, basis_b, radius, count=24)
    shell = VGroup()
    for index in range(len(ring)):
        next_index = (index + 1) % len(ring)
        face = Polygon(
            source,
            ring[index],
            ring[next_index],
            stroke_width=0.0,
            fill_color=shell_color,
            fill_opacity=shell_opacity,
        )
        face.set_shade_in_3d(True)
        shell.add(face)

    rim = VMobject(stroke_color=rim_color, stroke_width=rim_width, stroke_opacity=0.88)
    rim.set_points_as_corners([*ring, ring[0]])
    rim.set_shade_in_3d(True)
    shell.add(rim)
    return shell


def _build_ring(center, basis_a, basis_b, radius: float, *, count: int):
    points = []
    for index in range(count):
        angle = (2.0 * math.pi * index) / count
        offset = _scale(
            _add(_scale(basis_a, math.cos(angle)), _scale(basis_b, math.sin(angle))),
            radius,
        )
        points.append(_add(center, offset))
    return points


def _lon_lat_to_xyz(lon_deg: float, lat_deg: float, radius: float):
    lon = math.radians(lon_deg)
    lat = math.radians(lat_deg)
    return [
        radius * math.cos(lat) * math.cos(lon),
        radius * math.cos(lat) * math.sin(lon),
        radius * math.sin(lat),
    ]


def _normalize(vector):
    x, y, z = vector[0], vector[1], vector[2]
    magnitude = math.sqrt((x * x) + (y * y) + (z * z))
    if magnitude == 0.0:
        return [0.0, 0.0, 1.0]
    return [x / magnitude, y / magnitude, z / magnitude]


def _tangent_basis(unit_vector):
    x, y, z = unit_vector[0], unit_vector[1], unit_vector[2]
    reference = [0.0, 0.0, 1.0] if abs(z) < 0.88 else [0.0, 1.0, 0.0]
    basis_a = _normalize(_cross(reference, [x, y, z]))
    basis_b = _normalize(_cross([x, y, z], basis_a))
    return basis_a, basis_b


def _cross(left, right):
    return [
        (left[1] * right[2]) - (left[2] * right[1]),
        (left[2] * right[0]) - (left[0] * right[2]),
        (left[0] * right[1]) - (left[1] * right[0]),
    ]


def _add(left, right):
    return [left[0] + right[0], left[1] + right[1], left[2] + right[2]]


def _scale(vector, factor: float):
    return [vector[0] * factor, vector[1] * factor, vector[2] * factor]


def _lerp(left: float, right: float, alpha: float) -> float:
    return left + ((right - left) * alpha)


def _lerp_longitude(left: float, right: float, alpha: float) -> float:
    delta = ((right - left + 180.0) % 360.0) - 180.0
    value = left + (delta * alpha)
    return ((value + 180.0) % 360.0) - 180.0


def _event_color(kind: str) -> str:
    if kind == "total":
        return "#ff4b4b"
    if kind == "annular":
        return "#4c74ff"
    if kind == "partial":
        return "#f5d04f"
    return "#c95cff"
'''

