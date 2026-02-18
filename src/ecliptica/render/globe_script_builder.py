"""Build the globe scene script source."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def build_globe_script(payload_path: Path) -> str:
    """Build the 3D globe scene script."""
    template = """
from __future__ import annotations

import bisect
import json
import math

from manim import (
    DEGREES,
    DOWN,
    GREEN_C,
    ORANGE,
    UP,
    WHITE,
    Create,
    Dot3D,
    FadeIn,
    Line3D,
    Sphere,
    Text,
    ThreeDScene,
    VGroup,
    VMobject,
    ValueTracker,
    Write,
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
        if not samples:
            raise RuntimeError("Globe scene requires precomputed samples.")

        self.camera.background_color = "#060e1b"
        self.set_camera_orientation(phi=66 * DEGREES, theta=-118 * DEGREES, zoom=1.05)
        self.begin_ambient_camera_rotation(rate=0.07)

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
                "shadow_hits_earth": (
                    left["shadow_hits_earth"]
                    if alpha < 0.5
                    else right["shadow_hits_earth"]
                ),
            }

        earth = Sphere(
            radius=radius,
            resolution=(32, 64),
            fill_color="#123a67",
            fill_opacity=0.82,
            stroke_color="#8fb3d9",
            stroke_width=0.55,
        )
        coastline_mesh = _build_globe_coastlines(coastlines, radius + 0.003)
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
            color=GREEN_C,
        )
        cone = always_redraw(lambda: _build_shadow_cone(sample_at(tracker.get_value()), radius))

        title = Text("Ecliptica Globe View", font_size=34)
        subtitle = Text(
            event["event_kind"].title() + " eclipse shadow cone",
            font_size=24,
        )
        self.add_fixed_in_frame_mobjects(title, subtitle)
        title.to_edge(UP)
        subtitle.next_to(title, DOWN, buff=0.12)

        self.play(Write(title), FadeIn(subtitle))
        self.play(Create(earth), FadeIn(coastline_mesh))
        self.play(FadeIn(observer_dot), FadeIn(sun_dot), FadeIn(shadow_dot), FadeIn(cone))
        self.play(tracker.animate.set_value(duration), run_time=12.0, rate_func=linear)
        self.wait(0.8)
        self.stop_ambient_camera_rotation()


def _build_globe_coastlines(segments, radius: float):
    group = VGroup()
    for segment in segments[:450]:
        if len(segment) < 2:
            continue
        points = [_lon_lat_to_xyz(lon, lat, radius) for lon, lat in segment]
        curve = VMobject(stroke_color="#8fa9c6", stroke_width=0.7)
        curve.set_points_as_corners(points)
        group.add(curve)
    return group


def _build_shadow_cone(sample, radius: float):
    shadow_center = _lon_lat_to_xyz(sample["shadow_lon"], sample["shadow_lat"], radius + 0.06)
    sun_source = _lon_lat_to_xyz(sample["sun_lon"], sample["sun_lat"], radius + 4.1)
    axis = _normalize(shadow_center)
    basis_a, basis_b = _tangent_basis(axis)

    group = VGroup()
    group.add(Line3D(sun_source, shadow_center, color="#ffe6b0", thickness=0.022))
    cone_radius = 0.24 if sample["shadow_hits_earth"] else 0.34

    for index in range(8):
        angle = (2.0 * math.pi * index) / 8.0
        offset = _scale(
            _add(_scale(basis_a, math.cos(angle)), _scale(basis_b, math.sin(angle))),
            cone_radius,
        )
        ring_point = _add(shadow_center, offset)
        beam = Line3D(sun_source, ring_point, color="#fff2cf", thickness=0.010)
        beam.set_opacity(0.38)
        group.add(beam)
    return group


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
"""
    return template.replace("__PAYLOAD_PATH__", payload_path.as_posix())
