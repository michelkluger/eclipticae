"""Core eclipse computations and timeline sampling."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from astronomy import EclipseEvent as AstronomyEclipseEvent
from astronomy import EclipseKind, Observer, SearchLocalSolarEclipse, Time

from eclipticae.models import EclipseEvent, EclipseKindName, TimelinePoint


def compute_site_eclipse(
    *,
    latitude: float,
    longitude: float,
    date_or_datetime: date | datetime | str,
    elevation_m: float = 0.0,
) -> EclipseEvent:
    """Compute the next local solar eclipse for an observer from a start datetime."""
    start_utc = _coerce_utc_datetime(date_or_datetime)
    observer = Observer(latitude, longitude, elevation_m)
    info = SearchLocalSolarEclipse(_to_astronomy_time(start_utc), observer)

    return EclipseEvent(
        latitude=latitude,
        longitude=longitude,
        elevation_m=elevation_m,
        search_start_utc=start_utc,
        event_kind=_map_kind(info.kind),
        obscuration=float(info.obscuration),
        peak_utc=_ensure_utc(info.peak.time.Utc()),
        peak_altitude_deg=float(info.peak.altitude),
        partial_begin_utc=_event_time_or_none(info.partial_begin),
        partial_end_utc=_event_time_or_none(info.partial_end),
        total_begin_utc=_event_time_or_none(info.total_begin),
        total_end_utc=_event_time_or_none(info.total_end),
    )


def build_timeline(event: EclipseEvent, *, step_minutes: int = 5) -> list[TimelinePoint]:
    """Build evenly spaced timeline points between eclipse start and end."""
    if step_minutes <= 0:
        msg = "step_minutes must be greater than zero"
        raise ValueError(msg)

    start = event.partial_begin_utc or event.total_begin_utc or event.peak_utc
    end = event.partial_end_utc or event.total_end_utc or event.peak_utc

    if end <= start:
        return [TimelinePoint(utc=start, minutes_from_start=0.0, progress=1.0)]

    total_seconds = (end - start).total_seconds()
    step_seconds = float(step_minutes * 60)
    points: list[TimelinePoint] = []
    elapsed = 0.0
    while elapsed < total_seconds:
        point_time = start + _seconds_to_delta(elapsed)
        points.append(
            TimelinePoint(
                utc=point_time,
                minutes_from_start=elapsed / 60.0,
                progress=elapsed / total_seconds,
            ),
        )
        elapsed += step_seconds

    points.append(
        TimelinePoint(
            utc=end,
            minutes_from_start=total_seconds / 60.0,
            progress=1.0,
        ),
    )
    return points


def _coerce_utc_datetime(value: date | datetime | str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed_date = date.fromisoformat(value)
            return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _to_astronomy_time(value: datetime) -> Time:
    second = value.second + (value.microsecond / 1_000_000.0)
    return Time.Make(value.year, value.month, value.day, value.hour, value.minute, second)


def _map_kind(kind: EclipseKind) -> EclipseKindName:
    if kind == EclipseKind.Partial:
        return "partial"
    if kind == EclipseKind.Annular:
        return "annular"
    if kind == EclipseKind.Total:
        return "total"
    return "unknown"


def _event_time_or_none(event: AstronomyEclipseEvent | None) -> datetime | None:
    if event is None:
        return None
    return _ensure_utc(event.time.Utc())


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _seconds_to_delta(seconds: float) -> timedelta:
    return timedelta(seconds=seconds)
