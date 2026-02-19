"""Tests for global eclipse lookup and Saros projection helpers."""

from __future__ import annotations

from ecliptica.catalog import list_global_solar_eclipses, lookup_eclipse_with_saros

_CATALOG_YEAR = 2026
_SAROS_CYCLE_ENTRY_COUNT = 3


def test_list_global_solar_eclipses_stays_within_year() -> None:
    """Global eclipse listing should only include peaks in the requested UTC year."""
    events = list_global_solar_eclipses(_CATALOG_YEAR)
    if len(events) < 1:
        raise AssertionError
    if not all(event.peak_utc.year == _CATALOG_YEAR for event in events):
        raise AssertionError


def test_lookup_eclipse_with_saros_includes_anchor_cycle() -> None:
    """Lookup response should include the matched eclipse at Saros offset zero."""
    payload = lookup_eclipse_with_saros(
        year=_CATALOG_YEAR,
        name="annular",
        saros_span=1,
        window_days=60,
    )
    match = payload["match"]
    saros_cycle = payload["saros_cycle"]
    if len(saros_cycle) != _SAROS_CYCLE_ENTRY_COUNT:
        raise AssertionError

    anchor_candidates = [entry for entry in saros_cycle if entry["cycle_offset"] == 0]
    if len(anchor_candidates) != 1:
        raise AssertionError
    anchor = anchor_candidates[0]
    if anchor["eclipse"] is None:
        raise AssertionError
    if anchor["eclipse"]["eclipse_id"] != match["eclipse_id"]:
        raise AssertionError


def test_lookup_eclipse_with_saros_rejects_empty_name_query() -> None:
    """Lookup should fail fast when name query is empty or whitespace."""
    try:
        lookup_eclipse_with_saros(
            year=_CATALOG_YEAR,
            name="   ",
            saros_span=1,
            window_days=60,
        )
    except ValueError as exc:
        if "cannot be empty" not in str(exc):
            raise AssertionError from exc
        return
    raise AssertionError
