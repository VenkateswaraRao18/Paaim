"""Audit Agent — append-only demo audit log of scenario + gate + draft events."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo_scenario", "line3_rescue")
_LOG = os.path.join(_DATA, "demo_audit_log.json")


def append_event(event: Dict[str, Any]) -> Dict[str, Any]:
    event = {"timestamp": datetime.utcnow().isoformat(), **event}
    try:
        with open(_LOG) as f:
            data = json.load(f)
    except Exception:
        data = {"events": []}
    data["events"].append(event)
    data["events"] = data["events"][-200:]  # keep it bounded for the demo
    with open(_LOG, "w") as f:
        json.dump(data, f, indent=2)
    return event


def list_events(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        with open(_LOG) as f:
            return list(reversed(json.load(f)["events"]))[:limit]
    except Exception:
        return []
