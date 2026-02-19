# ruff: noqa: Q001
"""Render scene template source."""

from __future__ import annotations

TEMPLATE = '''from __future__ import annotations

import bisect
import json
import math
import random
from datetime import datetime

from manim import (
    BLACK,
    DOWN,
    FadeIn,
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
        land_polygons = payload.get("land_polygons", [])
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
                "penumbra_radius_km": _lerp(
                    left["penumbra_radius_km"],
                    right["penumbra_radius_km"],
                    alpha,
                ),
                "core_radius_km": _lerp(left["core_radius_km"], right["core_radius_km"], alpha),
                "core_kind": left["core_kind"] if alpha < 0.5 else right["core_kind"],
            }

        focus = sample_at(peak_seconds)
        focus_point = lon_lat_to_point(focus["shadow_lon"], focus["shadow_lat"])
        event_color = _event_color(event.get("event_kind", "unknown"))

        stars = _build_starfield()
        map_backlight = Rectangle(
            width=map_width + 0.4,
            height=map_height + 0.4,
            stroke_width=0.0,
            fill_color="#143b5c",
            fill_opacity=0.18,
        ).set_z_index(2)
        map_panel = Rectangle(
            width=map_width,
            height=map_height,
            stroke_color="#9eb9cd",
            stroke_width=1.15,
            fill_color="#0b2438",
            fill_opacity=1.0,
        ).set_z_index(3)
        water_top_light = Rectangle(
            width=map_width,
            height=map_height * 0.56,
            stroke_width=0.0,
            fill_color="#2f6d94",
            fill_opacity=0.24,
        ).align_to(map_panel, UP).set_z_index(4)
        water_bottom_depth = Rectangle(
            width=map_width,
            height=map_height * 0.62,
            stroke_width=0.0,
            fill_color="#05131f",
            fill_opacity=0.36,
        ).align_to(map_panel, DOWN).set_z_index(4)

        grid = VGroup()
        for lon in range(-150, 180, 30):
            grid.add(
                Line(
                    lon_lat_to_point(lon, -90),
                    lon_lat_to_point(lon, 90),
                    stroke_width=0.38,
                    stroke_opacity=0.24,
                    color="#89a9c0",
                )
            )
        for lat in range(-60, 90, 30):
            grid.add(
                Line(
                    lon_lat_to_point(-180, lat),
                    lon_lat_to_point(180, lat),
                    stroke_width=0.38,
                    stroke_opacity=0.24,
                    color="#89a9c0",
                )
            )
        grid.set_z_index(7)
        map_labels = _build_map_labels(lon_lat_to_point)
        map_labels.set_z_index(10)

        land = VGroup()
        for polygon in land_polygons:
            if len(polygon) < 3:
                continue
            points = [lon_lat_to_point(lon, lat) for lon, lat in polygon]
            continent = Polygon(
                *points,
                stroke_width=0.0,
                fill_color="#476f4c",
                fill_opacity=0.88,
            )
            land.add(continent)
        land.set_z_index(5)

        coastlines_halo = VGroup()
        coastlines = VGroup()
        for segment in coastline_segments:
            if len(segment) < 2:
                continue
            points = [lon_lat_to_point(lon, lat) for lon, lat in segment]
            halo = VMobject(stroke_color="#071522", stroke_width=2.5, stroke_opacity=0.62)
            halo.set_points_as_corners(points)
            coastlines_halo.add(halo)
            line = VMobject(stroke_color="#d7e8dc", stroke_width=0.82, stroke_opacity=0.92)
            line.set_points_as_corners(points)
            coastlines.add(line)
        coastlines_halo.set_z_index(8)
        coastlines.set_z_index(9)
        subsolar_track = _build_track(
            samples,
            "sun_lon",
            "sun_lat",
            lon_lat_to_point,
            color="#ffb347",
            stroke_width=0.7,
            stroke_opacity=0.72,
        ).set_z_index(30)
        centerline_track = _build_track(
            samples,
            "shadow_lon",
            "shadow_lat",
            lon_lat_to_point,
            color=event_color,
            stroke_width=1.35,
            stroke_opacity=0.95,
        ).set_z_index(31)
        penumbra_north_track = _build_track(
            samples,
            "penumbra_north_lon",
            "penumbra_north_lat",
            lon_lat_to_point,
            color="#d9e5f4",
            stroke_width=0.76,
            stroke_opacity=0.62,
        ).set_z_index(29)
        penumbra_south_track = _build_track(
            samples,
            "penumbra_south_lon",
            "penumbra_south_lat",
            lon_lat_to_point,
            color="#d9e5f4",
            stroke_width=0.76,
            stroke_opacity=0.62,
        ).set_z_index(29)
        core_north_track = _build_track(
            samples,
            "core_north_lon",
            "core_north_lat",
            lon_lat_to_point,
            color="#f4f8ff",
            stroke_width=0.94,
            stroke_opacity=0.82,
        ).set_z_index(30)
        core_south_track = _build_track(
            samples,
            "core_south_lon",
            "core_south_lat",
            lon_lat_to_point,
            color="#f4f8ff",
            stroke_width=0.94,
            stroke_opacity=0.82,
        ).set_z_index(30)

        tracker = ValueTracker(0.0)
        night_overlay = always_redraw(
            lambda: _build_night_overlay(sample_at(tracker.get_value()), lon_lat_to_point)
        )
        night_overlay.set_z_index(6)
        sun_glow = always_redraw(
            lambda: Circle(
                radius=0.22,
                stroke_width=0.0,
                fill_color="#ffb347",
                fill_opacity=0.2,
            ).set_z_index(41).move_to(
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
            ).set_z_index(43)
        )
        shadow_group = always_redraw(
            lambda: _build_eclipse_regions(
                sample_at(tracker.get_value()),
                lon_lat_to_point,
                map_width,
                tracker.get_value(),
            )
        )

        metric = Text(
            "obscuration " + str(round(float(event["obscuration"]), 3)),
            font_size=22,
            color="#a8c1dd",
        ).to_corner(UR).shift((LEFT * 0.2) + (DOWN * 0.1))
        duration_text = Text(
            _duration_label(event),
            font_size=20,
            color="#c0d3e4",
        ).next_to(metric, DOWN, buff=0.08).align_to(metric, RIGHT)

        observer_color = "#ff4fb3"
        observer = Dot(
            lon_lat_to_point(event["longitude"], event["latitude"]),
            radius=0.052,
            color=observer_color,
        ).set_z_index(44)
        observer_label = Text("observer", font_size=20, color=observer_color).next_to(
            observer, UP, buff=0.1
        ).set_z_index(44)
        time_text = always_redraw(
            lambda: Text(
                "UTC " + _format_utc(sample_at(tracker.get_value())["utc"]),
                font_size=23,
                color="#dce5f2",
            ).to_corner(RIGHT + DOWN).shift(UP * 0.05).set_z_index(60)
        )
        status_text = always_redraw(
            lambda: Text(
                _status(sample_at(tracker.get_value())),
                font_size=21,
                color="#dce5f2",
            ).to_corner(UR).shift(DOWN * 0.65).set_z_index(60)
        )
        legend = VGroup(
            _legend_entry(event_color, "centerline"),
            _legend_entry("#d9e5f4", "penumbra limits"),
            _legend_entry("#f4f8ff", "core limits"),
            _legend_entry("#ffb347", "subsolar"),
            _legend_entry(observer_color, "observer"),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.06).to_corner(UL).shift(
            DOWN * 0.6,
        ).set_z_index(60)
        kind_legend = VGroup(
            _legend_entry(_event_color("total"), "total"),
            _legend_entry(_event_color("annular"), "annular"),
            _legend_entry(_event_color("partial"), "partial"),
            _legend_entry(_event_color("unknown"), "hybrid/unknown"),
        ).arrange(RIGHT, buff=0.18).to_edge(DOWN).shift(UP * 0.24).set_z_index(60)

        map_static = VGroup(
            map_backlight,
            map_panel,
            water_top_light,
            water_bottom_depth,
            land,
            night_overlay,
            grid,
            map_labels,
            coastlines_halo,
            coastlines,
            penumbra_north_track,
            penumbra_south_track,
            core_north_track,
            core_south_track,
            subsolar_track,
            centerline_track,
        )

        self.camera.frame.set(width=14.2)
        self.play(FadeIn(stars, run_time=0.9))
        self.play(
            FadeIn(metric),
            FadeIn(duration_text),
        )
        self.play(
            LaggedStart(
                FadeIn(map_backlight),
                Create(map_panel),
                FadeIn(water_top_light),
                FadeIn(water_bottom_depth),
                FadeIn(land),
                FadeIn(night_overlay),
                FadeIn(grid),
                FadeIn(map_labels),
                FadeIn(coastlines_halo),
                FadeIn(coastlines),
                Create(penumbra_north_track),
                Create(penumbra_south_track),
                Create(core_north_track),
                Create(core_south_track),
                Create(subsolar_track),
                Create(centerline_track),
                lag_ratio=0.11,
            )
        )
        self.play(FadeIn(observer), FadeIn(observer_label))
        self.play(FadeIn(sun_glow), FadeIn(sun_dot), FadeIn(shadow_group))
        self.bring_to_front(sun_glow, shadow_group, sun_dot, observer, observer_label)
        self.play(FadeIn(time_text), FadeIn(status_text), FadeIn(legend), FadeIn(kind_legend))

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


def _build_track(
    samples,
    lon_key,
    lat_key,
    lon_lat_to_point,
    *,
    color,
    stroke_width,
    stroke_opacity=1.0,
):
    segments = VGroup()
    current_points = []
    previous_lon = None
    for sample in samples:
        lon = float(sample[lon_key])
        lat = float(sample[lat_key])
        if previous_lon is not None and abs(lon - previous_lon) > 170.0:
            if len(current_points) >= 2:
                curve = VMobject(
                    stroke_color=color,
                    stroke_width=stroke_width,
                    stroke_opacity=stroke_opacity,
                )
                curve.set_points_as_corners(current_points)
                segments.add(curve)
            current_points = []
        current_points.append(lon_lat_to_point(lon, lat))
        previous_lon = lon
    if len(current_points) >= 2:
        curve = VMobject(
            stroke_color=color,
            stroke_width=stroke_width,
            stroke_opacity=stroke_opacity,
        )
        curve.set_points_as_corners(current_points)
        segments.add(curve)
    return segments


def _build_map_labels(lon_lat_to_point):
    labels = VGroup()
    for lon in range(-120, 181, 60):
        label_text = str(abs(lon)) + ("W" if lon < 0 else ("E" if lon > 0 else ""))
        if lon == 0:
            label_text = "0"
        label = Text(label_text, font_size=14, color="#92aac0")
        label.move_to(lon_lat_to_point(lon, -84))
        labels.add(label)
    for lat in (-60, -30, 0, 30, 60):
        label_text = str(abs(lat)) + ("S" if lat < 0 else ("N" if lat > 0 else ""))
        if lat == 0:
            label_text = "0"
        label = Text(label_text, font_size=14, color="#92aac0")
        label.move_to(lon_lat_to_point(-171, lat))
        labels.add(label)
    return labels


def _legend_entry(color: str, text: str):
    return VGroup(
        Line(LEFT * 0.2, RIGHT * 0.2, stroke_color=color, stroke_width=2.2),
        Text(text, font_size=17, color="#dce5f2"),
    ).arrange(RIGHT, buff=0.12)


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


def _build_eclipse_regions(sample, lon_lat_to_point, map_width: float, seconds: float):
    center = lon_lat_to_point(sample["shadow_lon"], sample["shadow_lat"])
    km_to_units = map_width / 40075.0
    penumbra_radius = max(float(sample["penumbra_radius_km"]) * km_to_units, 0.06)
    core_radius = max(float(sample["core_radius_km"]) * km_to_units, 0.02)

    penumbra = Circle(
        radius=penumbra_radius,
        stroke_width=1.4,
        stroke_color="#e6ecf5",
        stroke_opacity=0.62,
        fill_color="#d7dfee",
        fill_opacity=0.2,
    ).move_to(center).set_z_index(40)
    penumbra_edge = Circle(
        radius=penumbra_radius,
        stroke_width=0.9,
        stroke_color="#f2f5fb",
        stroke_opacity=0.9,
        fill_opacity=0.0,
    ).move_to(center).set_z_index(41)

    group = VGroup(penumbra, penumbra_edge)
    core_kind = sample.get("core_kind", "umbra")
    if core_kind == "umbra":
        group.add(
            Circle(
                radius=core_radius,
                stroke_width=1.0,
                stroke_color="#ffffff",
                stroke_opacity=0.95,
                fill_color="#0c1424",
                fill_opacity=0.62,
            ).move_to(center).set_z_index(42)
        )
    else:
        group.add(
            Circle(
                radius=core_radius,
                stroke_width=1.3,
                stroke_color="#fff1cc",
                stroke_opacity=0.9,
                fill_color="#fff1cc",
                fill_opacity=0.13,
            ).move_to(center).set_z_index(42)
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
    core_label = "umbra" if sample.get("core_kind") == "umbra" else "antumbra"
    if sample["shadow_hits_earth"]:
        return core_label + " axis intersects Earth"
    return (
        core_label
        + " axis misses Earth by "
        + str(round(float(sample["shadow_miss_km"]), 1))
        + " km"
    )


def _duration_label(event) -> str:
    partial_minutes = _duration_minutes(
        event.get("partial_begin_utc"),
        event.get("partial_end_utc"),
    )
    total_minutes = _duration_minutes(
        event.get("total_begin_utc"),
        event.get("total_end_utc"),
    )
    partial_text = "partial " + str(round(partial_minutes, 1)) + " min"
    if total_minutes > 0.0:
        return partial_text + " | core " + str(round(total_minutes, 1)) + " min"
    return partial_text + " | core 0.0 min"


def _duration_minutes(start_raw, end_raw) -> float:
    if not start_raw or not end_raw:
        return 0.0
    start = _parse_utc(start_raw)
    end = _parse_utc(end_raw)
    return max((end - start).total_seconds() / 60.0, 0.0)


def _format_utc(raw: str) -> str:
    return _parse_utc(raw).strftime("%Y-%m-%d %H:%M:%S")


def _event_color(kind: str) -> str:
    if kind == "total":
        return "#ff4b4b"
    if kind == "annular":
        return "#4c74ff"
    if kind == "partial":
        return "#f5d04f"
    return "#c95cff"
'''

