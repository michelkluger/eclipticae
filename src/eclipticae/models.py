"""Typed data models for eclipse events and timeline points."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

EclipseKindName = Literal["partial", "annular", "total", "unknown"]


@dataclass(frozen=True, slots=True)
class EclipseEvent:
    """Computed local eclipse circumstances for one observer location."""

    latitude: float
    longitude: float
    elevation_m: float
    search_start_utc: datetime
    event_kind: EclipseKindName
    obscuration: float
    peak_utc: datetime
    peak_altitude_deg: float
    partial_begin_utc: datetime | None
    partial_end_utc: datetime | None
    total_begin_utc: datetime | None
    total_end_utc: datetime | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, datetime):
                payload[key] = _serialize_datetime(value)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EclipseEvent:
        """Build an instance from a JSON dictionary."""
        normalized: dict[str, Any] = dict(payload)
        datetime_keys = {
            "search_start_utc",
            "peak_utc",
            "partial_begin_utc",
            "partial_end_utc",
            "total_begin_utc",
            "total_end_utc",
        }
        for key in datetime_keys:
            value = normalized.get(key)
            if value is None:
                continue
            normalized[key] = datetime.fromisoformat(value)
        return cls(**normalized)


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    """Single sampled point on an eclipse timeline."""

    utc: datetime
    minutes_from_start: float
    progress: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "utc": _serialize_datetime(self.utc),
            "minutes_from_start": self.minutes_from_start,
            "progress": self.progress,
        }


def _serialize_datetime(value: datetime) -> str:
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc_value.isoformat().replace("+00:00", "Z")
