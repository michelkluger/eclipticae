# ruff: noqa: Q001
"""Render scene template source."""

from __future__ import annotations

TEMPLATE = '''from __future__ import annotations

import json

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UL,
    UP,
    UR,
    Create,
    FadeIn,
    LaggedStart,
    Line,
    MovingCameraScene,
    Polygon,
    Rectangle,
    Text,
    Transform,
    VGroup,
    VMobject,
)


class SarosMapScene(MovingCameraScene):
    def construct(self):
        with open("__PAYLOAD_PATH__", "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)

        events = payload.get("events", [])
        coastline_segments = payload.get("coastline_segments", [])
        land_polygons = payload.get("land_polygons", [])
        anchor = payload.get("anchor", {})
        if not events:
            raise RuntimeError("Saros scene requires at least one event.")

        self.camera.background_color = "#07101e"
        map_width = 12.4
        map_height = 6.2
        half_width = map_width / 2.0
        half_height = map_height / 2.0
        self.camera.frame.set(width=14.2)

        def lon_lat_to_point(lon: float, lat: float):
            x = (lon / 180.0) * half_width
            y = (lat / 90.0) * half_height
            return [x, y, 0]

        map_backlight = Rectangle(
            width=map_width + 0.4,
            height=map_height + 0.4,
            stroke_width=0.0,
            fill_color="#143b5c",
            fill_opacity=0.18,
        )
        map_panel = Rectangle(
            width=map_width,
            height=map_height,
            stroke_color="#9eb9cd",
            stroke_width=1.1,
            fill_color="#0b2438",
            fill_opacity=1.0,
        )
        water_top = Rectangle(
            width=map_width,
            height=map_height * 0.56,
            stroke_width=0.0,
            fill_color="#2f6d94",
            fill_opacity=0.22,
        ).align_to(map_panel, UP)
        water_bottom = Rectangle(
            width=map_width,
            height=map_height * 0.62,
            stroke_width=0.0,
            fill_color="#05131f",
            fill_opacity=0.34,
        ).align_to(map_panel, DOWN)

        grid = VGroup()
        for lon in range(-150, 180, 30):
            grid.add(
                Line(
                    lon_lat_to_point(lon, -90),
                    lon_lat_to_point(lon, 90),
                    stroke_width=0.35,
                    stroke_opacity=0.22,
                    color="#89a9c0",
                )
            )
        for lat in range(-60, 90, 30):
            grid.add(
                Line(
                    lon_lat_to_point(-180, lat),
                    lon_lat_to_point(180, lat),
                    stroke_width=0.35,
                    stroke_opacity=0.22,
                    color="#89a9c0",
                )
            )
        labels = _build_map_labels(lon_lat_to_point)

        land = VGroup()
        for polygon in land_polygons:
            if len(polygon) < 3:
                continue
            points = [lon_lat_to_point(lon, lat) for lon, lat in polygon]
            land.add(
                Polygon(
                    *points,
                    stroke_width=0.0,
                    fill_color="#4a724e",
                    fill_opacity=0.88,
                )
            )

        coast_halo = VGroup()
        coast = VGroup()
        for segment in coastline_segments:
            if len(segment) < 2:
                continue
            points = [lon_lat_to_point(lon, lat) for lon, lat in segment]
            halo = VMobject(stroke_color="#071522", stroke_width=2.3, stroke_opacity=0.6)
            halo.set_points_as_corners(points)
            coast_halo.add(halo)
            line = VMobject(stroke_color="#d7e8dc", stroke_width=0.78, stroke_opacity=0.92)
            line.set_points_as_corners(points)
            coast.add(line)

        static_map = VGroup(
            map_backlight,
            map_panel,
            water_top,
            water_bottom,
            land,
            grid,
            labels,
            coast_halo,
            coast,
        )
        static_map.set_z_index(8)

        anchor_text = Text(
            _anchor_label(payload, anchor),
            font_size=18,
            color="#dce5f2",
        ).to_corner(UL).shift(DOWN * 0.2)
        info_text = Text(" ", font_size=19, color="#dce5f2").to_corner(UR).shift(DOWN * 0.2)
        kind_legend = VGroup(
            _legend_entry(_event_color("total"), "total"),
            _legend_entry(_event_color("annular"), "annular"),
            _legend_entry(_event_color("partial"), "partial"),
            _legend_entry(_event_color("unknown"), "hybrid/unknown"),
        ).arrange(RIGHT, buff=0.18).to_edge(DOWN).shift(UP * 0.24)
        line_legend = VGroup(
            _legend_entry("#ffffff", "active centerline"),
            _legend_entry("#95a2b4", "past traces"),
        ).arrange(RIGHT, buff=0.18).to_edge(DOWN).shift(UP * 0.54)

        self.play(
            LaggedStart(
                FadeIn(map_backlight),
                Create(map_panel),
                FadeIn(water_top),
                FadeIn(water_bottom),
                FadeIn(land),
                FadeIn(grid),
                FadeIn(labels),
                FadeIn(coast_halo),
                FadeIn(coast),
                lag_ratio=0.1,
            )
        )
        self.play(FadeIn(anchor_text), FadeIn(info_text), FadeIn(kind_legend), FadeIn(line_legend))

        max_visible_trails = 10
        trail_lines = []
        all_lines = []
        for event in events:
            centerline = _build_event_centerline(event, lon_lat_to_point)
            centerline.set_z_index(40)
            all_lines.append(centerline)
            next_info = Text(
                _event_label(event),
                font_size=19,
                color="#dce5f2",
            ).to_corner(UR).shift(DOWN * 0.2)
            animations = [Transform(info_text, next_info), Create(centerline)]
            if trail_lines:
                animations.append(trail_lines[-1].animate.set_stroke(width=1.2, opacity=0.34))
            self.play(*animations, run_time=0.4)
            trail_lines.append(centerline)
            if len(trail_lines) > max_visible_trails:
                faded = trail_lines.pop(0)
                self.play(faded.animate.set_stroke(width=0.92, opacity=0.14), run_time=0.12)

        if all_lines:
            final_info = Text(
                "all paths combined (" + str(len(events)) + " events)",
                font_size=19,
                color="#dce5f2",
            ).to_corner(UR).shift(DOWN * 0.2)
            self.play(
                Transform(info_text, final_info),
                *[line.animate.set_stroke(width=1.05, opacity=0.28) for line in all_lines],
                run_time=0.8,
            )

        self.wait(0.9)


def _build_event_centerline(event, lon_lat_to_point):
    path = event["path"]
    event_color = _event_color(event.get("event_kind", "unknown"))
    return _build_polyline(
        path.get("centerline", []),
        lon_lat_to_point,
        color=event_color,
        stroke_width=2.2,
        stroke_opacity=0.97,
    )


def _build_polyline(
    points,
    lon_lat_to_point,
    *,
    color: str,
    stroke_width: float,
    stroke_opacity: float,
):
    group = VGroup()
    active = []
    previous_lon = None
    for lon, lat in points:
        lon_value = float(lon)
        lat_value = float(lat)
        if previous_lon is not None and abs(lon_value - previous_lon) > 170.0:
            if len(active) >= 2:
                segment = VMobject(
                    stroke_color=color,
                    stroke_width=stroke_width,
                    stroke_opacity=stroke_opacity,
                )
                segment.set_points_as_corners(active)
                segment.set_fill(opacity=0.0)
                group.add(segment)
            active = []
        active.append(lon_lat_to_point(lon_value, lat_value))
        previous_lon = lon_value
    if len(active) >= 2:
        segment = VMobject(
            stroke_color=color,
            stroke_width=stroke_width,
            stroke_opacity=stroke_opacity,
        )
        segment.set_points_as_corners(active)
        segment.set_fill(opacity=0.0)
        group.add(segment)
    return group


def _event_label(event) -> str:
    phase_days = float(event.get("saros_phase_days", 0.0))
    offset = int(event.get("saros_offset", 0))
    offset_text = "+" + str(offset) if offset >= 0 else str(offset)
    phase_text = ("+" if phase_days >= 0.0 else "") + str(round(phase_days, 2))
    return (
        event.get("peak_utc", "")[:10]
        + " "
        + event.get("event_kind", "unknown")
        + " | offset "
        + offset_text
        + " | phase "
        + phase_text
        + " d"
    )


def _anchor_label(payload, anchor) -> str:
    period_days = round(float(payload.get("saros_period_days", 6585.321667)), 6)
    return (
        "anchor "
        + anchor.get("peak_utc", "")[:10]
        + " "
        + anchor.get("event_kind", "unknown")
        + " | period "
        + str(period_days)
        + " d"
    )


def _build_map_labels(lon_lat_to_point):
    labels = VGroup()
    for lon in range(-120, 181, 60):
        label_text = str(abs(lon)) + ("W" if lon < 0 else ("E" if lon > 0 else ""))
        if lon == 0:
            label_text = "0"
        label = Text(label_text, font_size=14, color="#92aac0")
        labels.add(label.move_to(lon_lat_to_point(lon, -84)))
    for lat in (-60, -30, 0, 30, 60):
        label_text = str(abs(lat)) + ("S" if lat < 0 else ("N" if lat > 0 else ""))
        if lat == 0:
            label_text = "0"
        label = Text(label_text, font_size=14, color="#92aac0")
        labels.add(label.move_to(lon_lat_to_point(-171, lat)))
    return labels


def _legend_entry(color: str, text: str):
    return VGroup(
        Line(LEFT * 0.2, RIGHT * 0.2, stroke_color=color, stroke_width=2.2),
        Text(text, font_size=16, color="#dce5f2"),
    ).arrange(RIGHT, buff=0.1)


def _event_color(kind: str) -> str:
    if kind == "total":
        return "#ff4b4b"
    if kind == "annular":
        return "#4c74ff"
    if kind == "partial":
        return "#f5d04f"
    return "#c95cff"
'''

