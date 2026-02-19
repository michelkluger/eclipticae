"""Global eclipse catalog lookup helpers with Saros-chain projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Literal

from astronomy import (
    EclipseKind,
    GlobalSolarEclipseInfo,
    NextGlobalSolarEclipse,
    SearchGlobalSolarEclipse,
)
from astronomy import Time as AstronomyTime

EclipseKindName = Literal["partial", "annular", "total", "unknown"]

_SAROS_PERIOD = timedelta(days=6585, hours=7, minutes=43, seconds=12)
_DEFAULT_SAROS_SPAN = 2
_DEFAULT_WINDOW_DAYS = 45
_MIN_MATCH_SCORE = 0.2


@dataclass(frozen=True, slots=True)
class GlobalEclipseRecord:
    """Serializable global eclipse metadata record."""

    eclipse_id: str
    name: str
    event_kind: EclipseKindName
    peak_utc: datetime
    latitude: float
    longitude: float
    distance_km: float
    obscuration: float | None

    def to_dict(self) -> dict[str, Any]:
        """Convert the record to a JSON-serializable dictionary."""
        return {
            "eclipse_id": self.eclipse_id,
            "name": self.name,
            "event_kind": self.event_kind,
            "peak_utc": _serialize_utc(self.peak_utc),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_km": self.distance_km,
            "obscuration": self.obscuration,
        }


def list_global_solar_eclipses(year: int) -> list[GlobalEclipseRecord]:
    """List all global solar eclipses with peak time inside one UTC year."""
    year_start = datetime(year, 1, 1, tzinfo=UTC)
    year_end = datetime(year + 1, 1, 1, tzinfo=UTC)

    eclipse = SearchGlobalSolarEclipse(_to_astronomy_time(year_start))
    events: list[GlobalEclipseRecord] = []
    while True:
        peak_utc = _ensure_utc(eclipse.peak.Utc())
        if peak_utc >= year_end:
            break
        if peak_utc >= year_start:
            events.append(_record_from_global_info(eclipse))
        eclipse = NextGlobalSolarEclipse(eclipse.peak)
    return events


def lookup_eclipse_with_saros(
    *,
    year: int,
    name: str,
    saros_span: int = _DEFAULT_SAROS_SPAN,
    window_days: int = _DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Find one eclipse in a year and combine nearby Saros-chain events."""
    if saros_span < 1:
        msg = "saros_span must be at least 1"
        raise ValueError(msg)
    if window_days < 1:
        msg = "window_days must be at least 1"
        raise ValueError(msg)

    year_events = list_global_solar_eclipses(year)
    if not year_events:
        msg = f"No global solar eclipses found in {year}."
        raise RuntimeError(msg)

    match = _select_best_match(year_events, name)
    saros_cycle = _build_saros_cycle(match, saros_span=saros_span, window_days=window_days)

    return {
        "query": {"year": year, "name": name},
        "match": match.to_dict(),
        "year_events": [event.to_dict() for event in year_events],
        "saros_period_days": round(_SAROS_PERIOD.total_seconds() / 86400.0, 6),
        "saros_cycle": saros_cycle,
    }


def _build_saros_cycle(
    anchor: GlobalEclipseRecord,
    *,
    saros_span: int,
    window_days: int,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for cycle_offset in range(-saros_span, saros_span + 1):
        target_utc = anchor.peak_utc + (cycle_offset * _SAROS_PERIOD)
        if cycle_offset == 0:
            matched = anchor
            delta_days = 0.0
        else:
            matched, delta_days = _find_nearest_global_eclipse(target_utc, window_days=window_days)
        entries.append(
            {
                "cycle_offset": cycle_offset,
                "target_utc": _serialize_utc(target_utc),
                "match_delta_days": delta_days,
                "eclipse": None if matched is None else matched.to_dict(),
            },
        )
    return entries


def _find_nearest_global_eclipse(
    target_utc: datetime,
    *,
    window_days: int,
) -> tuple[GlobalEclipseRecord | None, float | None]:
    search_start = target_utc - timedelta(days=window_days)
    search_end = target_utc + timedelta(days=window_days)
    eclipse = SearchGlobalSolarEclipse(_to_astronomy_time(search_start))

    nearest_event: GlobalEclipseRecord | None = None
    nearest_delta_seconds: float | None = None

    while True:
        peak_utc = _ensure_utc(eclipse.peak.Utc())
        if peak_utc > search_end:
            break
        delta_seconds = abs((peak_utc - target_utc).total_seconds())
        if nearest_delta_seconds is None or delta_seconds < nearest_delta_seconds:
            nearest_event = _record_from_global_info(eclipse)
            nearest_delta_seconds = delta_seconds
        eclipse = NextGlobalSolarEclipse(eclipse.peak)

    if nearest_event is None or nearest_delta_seconds is None:
        return None, None
    return nearest_event, round(nearest_delta_seconds / 86400.0, 6)


def _select_best_match(
    events: list[GlobalEclipseRecord],
    query_name: str,
) -> GlobalEclipseRecord:
    normalized_query = _normalize(query_name)
    if normalized_query == "":
        return events[0]

    ranked = sorted(
        ((_match_score(event, normalized_query), event) for event in events),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_event = ranked[0]
    if best_score < _MIN_MATCH_SCORE:
        available = ", ".join(event.name for event in events)
        msg = f"No eclipse name matched the query in this year. Try one of: {available}"
        raise ValueError(msg)
    return best_event


def _match_score(event: GlobalEclipseRecord, query_name: str) -> float:
    normalized_label = _normalize(event.name)
    similarity = SequenceMatcher(a=query_name, b=normalized_label).ratio()
    query_tokens = [token for token in query_name.split(" ") if token != ""]
    token_hits = sum(1 for token in query_tokens if token in normalized_label)
    contains_query = 1.0 if query_name in normalized_label else 0.0
    return similarity + (0.2 * float(token_hits)) + (0.75 * contains_query)


def _record_from_global_info(info: GlobalSolarEclipseInfo) -> GlobalEclipseRecord:
    peak_utc = _ensure_utc(info.peak.Utc())
    event_kind = _map_kind(info.kind)
    date_label = peak_utc.strftime("%Y-%m-%d")
    name = f"{date_label} {event_kind.title()} Solar Eclipse"
    eclipse_id = f"{peak_utc.strftime('%Y%m%d')}-{event_kind}"
    obscuration = None if info.obscuration is None else float(info.obscuration)
    distance_km = max(float(info.distance), 0.0)
    return GlobalEclipseRecord(
        eclipse_id=eclipse_id,
        name=name,
        event_kind=event_kind,
        peak_utc=peak_utc,
        latitude=float(info.latitude),
        longitude=float(info.longitude),
        distance_km=distance_km,
        obscuration=obscuration,
    )


def _map_kind(kind: EclipseKind) -> EclipseKindName:
    if kind == EclipseKind.Partial:
        return "partial"
    if kind == EclipseKind.Annular:
        return "annular"
    if kind == EclipseKind.Total:
        return "total"
    return "unknown"


def _to_astronomy_time(value: datetime) -> AstronomyTime:
    utc_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    utc_value = utc_value.astimezone(UTC)
    second = utc_value.second + (utc_value.microsecond / 1_000_000.0)
    return AstronomyTime.Make(
        utc_value.year,
        utc_value.month,
        utc_value.day,
        utc_value.hour,
        utc_value.minute,
        second,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _serialize_utc(value: datetime) -> str:
    utc_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return utc_value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())
