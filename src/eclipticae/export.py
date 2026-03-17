"""JSON import/export helpers for eclipse event data."""

from __future__ import annotations

from pathlib import Path

import msgspec
import orjson

from eclipticae.models import EclipseEvent


def save_event(event: EclipseEvent, output_path: str | Path) -> Path:
    """Serialize and save an eclipse event to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = orjson.dumps(event.to_dict(), option=orjson.OPT_INDENT_2) + b"\n"
    path.write_bytes(payload)
    return path


def load_event(input_path: str | Path) -> EclipseEvent:
    """Load an eclipse event from JSON."""
    path = Path(input_path)
    raw_payload = path.read_bytes()
    try:
        return msgspec.json.decode(raw_payload, type=EclipseEvent)
    except msgspec.ValidationError as exc:
        msg = f"Invalid eclipse event payload in {input_path}: {exc}"
        raise TypeError(msg) from exc
