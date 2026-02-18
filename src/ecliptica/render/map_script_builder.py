"""Build the map scene script source."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def build_map_script(payload_path: Path) -> str:
    """Build the 2D world-map scene script."""
    template = """
from __future__ import annotations

import bisect
import json
import math
import random
from datetime import datetime

from manim import (
    BLACK,
    BLUE_E,
    DOWN,
    FadeIn,
    GREEN_C,
    LEFT,
    ORANGE,
    RIGHT,
    UL,
    UP,
    UR,
    WHITE,
    Circle,
    Create,
    Dot,
    LaggedStart,
    Line,
    MovingCameraScene,
    Polygon,
    Rectangle,
    Text,
    VGroup,
    VMobject,
    ValueTracker,
    Write,
    always_redraw,
    linear,
    smooth,
)


class WorldMapScene(MovingCameraScene):
    def construct(self):
        with open("__PAYLOAD_PATH__", "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)

        event = payload["event"]
        samples = payload.get("samples", [])
        coastline_segments = payload.get("coastline_segments", [])
        if not samples:
            raise RuntimeError("Map scene requires precomputed samples.")

        self.camera.background_color = "#070f1f"
        map_width = 12.4
        map_height = 6.2
        half_width = map_width / 2.0
        half_height = map_height / 2.0
        duration = max(samples[-1]["seconds"], 1.0)
        seconds_axis = [item["seconds"] for item in samples]

        start_utc = _parse_utc(samples[0]["utc"])
        peak_utc = _parse_utc(event["peak_utc"])
        peak_seconds = _clamp((peak_utc - start_utc).total_seconds(), 0.0, duration)

        def lon_lat_to_point(lon: float, lat: float):
            x = (lon / 180.0) * half_width
            y = (lat / 90.0) * half_height
            return [x, y, 0]

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
                "seconds": seconds,
                "utc": left["utc"] if alpha < 0.5 else right["utc"],
                "sun_lon": _lerp_longitude(left["sun_lon"], right["sun_lon"], alpha),
                "sun_lat": _lerp(left["sun_lat"], right["sun_lat"], alpha),
                "shadow_lon": _lerp_longitude(left["shadow_lon"], right["shadow_lon"], alpha),
                "shadow_lat": _lerp(left["shadow_lat"], right["shadow_lat"], alpha),
                "shadow_hits_earth": (
                    left["shadow_hits_earth"]
                    if alpha < 0.5
                    else right["shadow_hits_earth"]
                ),
                "shadow_miss_km": _lerp(left["shadow_miss_km"], right["shadow_miss_km"], alpha),
            }

        focus = sample_at(peak_seconds)
        focus_point = lon_lat_to_point(focus["shadow_lon"], focus["shadow_lat"])

        stars = _build_starfield()
        map_backlight = Rectangle(
            width=map_width + 0.4,
            height=map_height + 0.4,
            stroke_width=0.0,
            fill_color="#0f2d52",
            fill_opacity=0.16,
        )
        map_panel = Rectangle(
            width=map_width,
            height=map_height,
            stroke_color="#a8c1dd",
            stroke_width=1.3,
            fill_color=BLUE_E,
            fill_opacity=0.5,
        )

        grid = VGroup()
        for lon in range(-150, 180, 30):
            grid.add(
                Line(
                    lon_lat_to_point(lon, -90),
                    lon_lat_to_point(lon, 90),
                    stroke_width=0.55,
                    color="#2a4f74",
                )
            )
        for lat in range(-60, 90, 30):
            grid.add(
                Line(
                    lon_lat_to_point(-180, lat),
                    lon_lat_to_point(180, lat),
                    stroke_width=0.55,
                    color="#2a4f74",
                )
            )

        coastlines = VGroup()
        for segment in coastline_segments:
            if len(segment) < 2:
                continue
            points = [lon_lat_to_point(lon, lat) for lon, lat in segment]
            line = VMobject(stroke_color="#8aa2b9", stroke_width=1.0)
            line.set_points_as_corners(points)
            coastlines.add(line)

        sun_track = _build_track(
            samples, "sun_lon", "sun_lat", lon_lat_to_point, color="#ffb347", stroke_width=2.0
        )
        shadow_track = _build_track(
            samples,
            "shadow_lon",
            "shadow_lat",
            lon_lat_to_point,
            color="#dce5f2",
            stroke_width=1.6,
        )

        tracker = ValueTracker(0.0)
        night_overlay = always_redraw(
            lambda: _build_night_overlay(sample_at(tracker.get_value()), lon_lat_to_point)
        )
        sun_glow = always_redraw(
            lambda: Circle(
                radius=0.22,
                stroke_width=0.0,
                fill_color="#ffb347",
                fill_opacity=0.2,
            ).move_to(
                lon_lat_to_point(
                    sample_at(tracker.get_value())["sun_lon"],
                    sample_at(tracker.get_value())["sun_lat"],
                )
            )
        )
        sun_dot = always_redraw(
            lambda: Dot(
                lon_lat_to_point(
                    sample_at(tracker.get_value())["sun_lon"],
                    sample_at(tracker.get_value())["sun_lat"],
                ),
                radius=0.075,
                color=ORANGE,
            )
        )
        shadow_group = always_redraw(
            lambda: _build_shadow_group(
                sample_at(tracker.get_value()),
                lon_lat_to_point,
                map_width,
                tracker.get_value(),
            )
        )

        title = Text("Ecliptica", font_size=52).to_edge(UP).shift(DOWN * 0.05)
        subtitle = Text(
            event["event_kind"].title() + " eclipse shadow map",
            font_size=28,
        ).next_to(title, DOWN, buff=0.14)
        metric = Text(
            "obscuration " + str(round(float(event["obscuration"]), 3)),
            font_size=22,
            color="#a8c1dd",
        ).next_to(subtitle, DOWN, buff=0.08)

        observer = Dot(
            lon_lat_to_point(event["longitude"], event["latitude"]),
            radius=0.052,
            color=GREEN_C,
        )
        observer_label = Text("observer", font_size=20, color=GREEN_C).next_to(
            observer, UP, buff=0.1
        )
        time_text = always_redraw(
            lambda: Text(
                "UTC " + _format_utc(sample_at(tracker.get_value())["utc"]),
                font_size=23,
                color="#dce5f2",
            ).to_corner(RIGHT + DOWN).shift(UP * 0.05)
        )
        status_text = always_redraw(
            lambda: Text(
                _status(sample_at(tracker.get_value())),
                font_size=21,
                color="#dce5f2",
            ).to_corner(UR).shift(DOWN * 0.65)
        )
        legend = VGroup(
            Dot(radius=0.05, color=ORANGE),
            Text("subsolar", font_size=19),
            Dot(radius=0.05, color=WHITE),
            Text("shadow axis", font_size=19),
            Dot(radius=0.05, color=GREEN_C),
            Text("observer", font_size=19),
        ).arrange(RIGHT, buff=0.16).to_corner(UL).shift(DOWN * 0.62)

        map_static = VGroup(
            map_backlight,
            map_panel,
            night_overlay,
            grid,
            coastlines,
            sun_track,
            shadow_track,
        )

        self.camera.frame.set(width=14.2)
        self.play(FadeIn(stars, run_time=0.9))
        self.play(Write(title), FadeIn(subtitle, shift=DOWN * 0.18), FadeIn(metric))
        self.play(
            LaggedStart(
                FadeIn(map_backlight),
                Create(map_panel),
                FadeIn(night_overlay),
                FadeIn(grid),
                FadeIn(coastlines),
                Create(sun_track),
                Create(shadow_track),
                lag_ratio=0.11,
            )
        )
        self.play(FadeIn(observer), FadeIn(observer_label))
        self.play(FadeIn(sun_glow), FadeIn(sun_dot), FadeIn(shadow_group))
        self.play(FadeIn(time_text), FadeIn(status_text), FadeIn(legend))

        first_stop = max(duration * 0.58, peak_seconds)
        self.play(
            tracker.animate.set_value(first_stop),
            map_static.animate.scale(1.02),
            self.camera.frame.animate.move_to(focus_point).set(width=8.5),
            run_time=6.0,
            rate_func=smooth,
        )
        self.play(
            tracker.animate.set_value(duration),
            self.camera.frame.animate.move_to([0, 0, 0]).set(width=14.2),
            run_time=6.0,
            rate_func=linear,
        )
        self.wait(0.6)


def _build_starfield() -> VGroup:
    random.seed(14)
    stars = VGroup()
    for _ in range(160):
        stars.add(
            Dot(
                [random.uniform(-7.1, 7.1), random.uniform(-3.95, 3.95), 0],
                radius=random.uniform(0.006, 0.014),
                color="#d7e8ff",
                fill_opacity=random.uniform(0.18, 0.55),
                stroke_width=0,
            )
        )
    return stars


def _build_track(samples, lon_key, lat_key, lon_lat_to_point, *, color, stroke_width):
    segments = VGroup()
    current_points = []
    previous_lon = None
    for sample in samples:
        lon = float(sample[lon_key])
        lat = float(sample[lat_key])
        if previous_lon is not None and abs(lon - previous_lon) > 170.0:
            if len(current_points) >= 2:
                curve = VMobject(stroke_color=color, stroke_width=stroke_width)
                curve.set_points_as_corners(current_points)
                segments.add(curve)
            current_points = []
        current_points.append(lon_lat_to_point(lon, lat))
        previous_lon = lon
    if len(current_points) >= 2:
        curve = VMobject(stroke_color=color, stroke_width=stroke_width)
        curve.set_points_as_corners(current_points)
        segments.add(curve)
    return segments


def _build_night_overlay(sample, lon_lat_to_point):
    lons = list(range(-180, 181, 4))
    terminator = [
        (float(lon), _terminator_lat(float(lon), sample["sun_lon"], sample["sun_lat"]))
        for lon in lons
    ]
    north_night = _solar_cosine(
        lat_deg=85.0,
        lon_deg=sample["sun_lon"],
        sun_lat_deg=sample["sun_lat"],
        sun_lon_deg=sample["sun_lon"],
    ) <= 0.0
    if north_night:
        border = [(-180.0, 90.0), (180.0, 90.0)] + list(reversed(terminator))
    else:
        border = [(-180.0, -90.0), (180.0, -90.0)] + terminator
    polygon = Polygon(
        *[lon_lat_to_point(lon, lat) for lon, lat in border],
        stroke_width=0.0,
        fill_color=BLACK,
        fill_opacity=0.34,
    )
    edge = VMobject(stroke_color="#dce5f2", stroke_width=1.05, stroke_opacity=0.5)
    edge.set_points_as_corners([lon_lat_to_point(lon, lat) for lon, lat in terminator])
    return VGroup(polygon, edge)


def _terminator_lat(lon_deg, sun_lon_deg, sun_lat_deg):
    delta = math.radians(float(sun_lat_deg))
    if abs(math.sin(delta)) < 1e-6:
        return 0.0
    delta_lon = math.radians(lon_deg - sun_lon_deg)
    numerator = -math.cos(delta) * math.cos(delta_lon)
    denominator = math.sin(delta)
    return _clamp(math.degrees(math.atan2(numerator, denominator)), -89.9, 89.9)


def _solar_cosine(lat_deg, lon_deg, sun_lat_deg, sun_lon_deg):
    lat = math.radians(lat_deg)
    sun_lat = math.radians(sun_lat_deg)
    delta_lon = math.radians(lon_deg - sun_lon_deg)
    return (
        (math.sin(lat) * math.sin(sun_lat))
        + (math.cos(lat) * math.cos(sun_lat) * math.cos(delta_lon))
    )


def _build_shadow_group(sample, lon_lat_to_point, map_width: float, seconds: float):
    center = lon_lat_to_point(sample["shadow_lon"], sample["shadow_lat"])
    units_per_degree = map_width / 360.0
    pulse = 0.72 + (0.28 * (0.5 + 0.5 * math.sin(seconds * 0.11)))
    penumbra = Circle(
        radius=14.5 * units_per_degree * pulse,
        stroke_width=1.0,
        stroke_color="#dce5f2",
        fill_color="#dce5f2",
        fill_opacity=0.16,
    ).move_to(center)
    core = Circle(
        radius=6.1 * units_per_degree,
        stroke_width=0.0,
        fill_color="#ffffff",
        fill_opacity=0.09,
    ).move_to(center)
    group = VGroup(penumbra, core)
    if sample["shadow_hits_earth"]:
        group.add(
            Circle(
                radius=4.6 * units_per_degree,
                stroke_width=0.9,
                stroke_color="#ffffff",
                fill_color="#ffffff",
                fill_opacity=0.3,
            ).move_to(center)
        )
    else:
        group.add(
            Circle(
                radius=4.8 * units_per_degree,
                stroke_width=1.2,
                stroke_color="#ffffff",
                fill_opacity=0.0,
            ).move_to(center)
        )
    return group


def _parse_utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _lerp(left: float, right: float, alpha: float) -> float:
    return left + ((right - left) * alpha)


def _lerp_longitude(left: float, right: float, alpha: float) -> float:
    delta = ((right - left + 180.0) % 360.0) - 180.0
    value = left + (delta * alpha)
    return ((value + 180.0) % 360.0) - 180.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _status(sample) -> str:
    if sample["shadow_hits_earth"]:
        return "shadow axis intersects Earth"
    return "axis misses Earth by " + str(round(float(sample["shadow_miss_km"]), 1)) + " km"


def _format_utc(raw: str) -> str:
    return _parse_utc(raw).strftime("%Y-%m-%d %H:%M:%S")
"""
    return template.replace("__PAYLOAD_PATH__", payload_path.as_posix())
