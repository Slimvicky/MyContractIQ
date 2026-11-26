"""Append-only audit trail at output/audit_trail.json.

Format: JSON Lines (one JSON object per line) so entries are only ever appended,
never rewritten. Each entry carries a hash of the previous entry, so any edit or
deletion of history is detectable with `verify_chain()`.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any

from .config import AUDIT_TRAIL_PATH

_lock = threading.Lock()
SENSITIVE_KEYS = {"password", "confirm_password", "password_hash", "token", "api_key"}


def _scrub(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: ("[redacted]" if k.lower() in SENSITIVE_KEYS else _scrub(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [_scrub(v) for v in data]
    return data


def _last_hash() -> str:
    if not AUDIT_TRAIL_PATH.exists():
        return "GENESIS"
    last = ""
    with AUDIT_TRAIL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line
    if not last:
        return "GENESIS"
    try:
        return json.loads(last).get("hash", "GENESIS")
    except json.JSONDecodeError:
        return "CORRUPT"


def record(event: str, user_id: int | None = None, **details: Any) -> None:
    with _lock:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "user_id": user_id,
            "details": _scrub(details),
            "prev_hash": _last_hash(),
        }
        body = json.dumps(entry, sort_keys=True, default=str)
        entry["hash"] = hashlib.sha256(body.encode()).hexdigest()
        # "a" mode: the OS only ever appends to the end of the file.
        with AUDIT_TRAIL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")


def verify_chain() -> dict:
    if not AUDIT_TRAIL_PATH.exists():
        return {"ok": True, "entries": 0}
    prev = "GENESIS"
    n = 0
    with AUDIT_TRAIL_PATH.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            entry = json.loads(line)
            h = entry.pop("hash", None)
            body = json.dumps(entry, sort_keys=True, default=str)
            if entry.get("prev_hash") != prev or hashlib.sha256(body.encode()).hexdigest() != h:
                return {"ok": False, "entries": n, "broken_at_line": i}
            prev = h
            n += 1
    return {"ok": True, "entries": n}
