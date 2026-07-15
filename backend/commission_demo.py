"""
Commission both demo plants end to end, through PAAIM's own API.

Deliberately over HTTP rather than straight into the database: this walks the
exact path an operator walks — connect, discover, propose, confirm, ingest
context, upload history, create a monitor — so if commissioning is broken, this
fails loudly. A seeder that wrote rows directly would keep working while the
product it exists to demonstrate did not.

Note this is NOT seed_demo.py, which fabricates thirty days of events and
decisions so the analytics screens look busy. Nothing here is invented: the
incidents your professor sees will be real ones, raised by real watchers from
real readings, or there will be none.

Idempotent — safe on every `docker compose up`.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

API = os.getenv("PAAIM_API", "http://localhost:8000/api")

PLANTS: Dict[str, Dict[str, Any]] = {
    "northfield_foods": {
        "email": "ops@northfield.example", "password": "northfield123",
        "source_id": "northfield_scada",
        "endpoint": os.getenv("DEMO_STREAM_FOOD", "http://localhost:9100"),
        "context": "northfield_foods_context.json",
        "history": "northfield_foods_history.csv",
        "monitor": {
            "name": "Pasteuriser & Fill Quality", "domain": "quality",
            "description": "Wakes on product temperature or fill weight, anywhere on the line.",
            "watch_signals": ["product_temperature", "fill_weight"],
            "rules": [{"field": "fill_weight", "operator": ">", "value": "508",
                       "action": "hold_batch", "confidence": 0.9, "priority": 1}],
        },
    },
    "precision_parts": {
        "email": "ops@precision.example", "password": "precision123",
        "source_id": "precision_scada",
        "endpoint": os.getenv("DEMO_STREAM_CNC", "http://localhost:9101"),
        "context": None,
        "history": None,
        "monitor": {
            "name": "Spindle Health", "domain": "maintenance",
            "description": "Wakes on vibration or temperature, fleet-wide.",
            "watch_signals": ["vibration", "temperature"],
            "rules": [{"field": "vibration", "operator": ">", "value": "3.5",
                       "action": "escalate", "confidence": 0.9, "priority": 1}],
        },
    },
}


def call(path: str, token: Optional[str] = None, method: str = "GET",
         body: Any = None) -> Tuple[int, Any]:
    req = urllib.request.Request(
        f"{API}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw, st = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, st = e.read(), e.code
    except urllib.error.URLError as e:
        return 0, {"detail": str(e)}
    try:
        return st, json.loads(raw or b"{}")
    except Exception:
        return st, {}


def upload_history(path: str, token: str, source_id: str) -> Tuple[int, Any]:
    """multipart by hand — the stdlib has no helper, and this is one field."""
    with open(path, "rb") as f:
        payload = f.read()
    b = "----paaim-commission-boundary"
    body = (
        f"--{b}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode() + payload + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/knowledge/history/upload?source_id={source_id}", method="POST", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={b}",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def wait_for_api(attempts: int = 60) -> bool:
    base = API.rsplit("/api", 1)[0]
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def commission(factory_id: str, cfg: Dict[str, Any]) -> None:
    st, d = call("/auth/login", method="POST",
                 body={"email": cfg["email"], "password": cfg["password"]})
    if st != 200:
        print(f"  [{factory_id}] login failed: {d}")
        return
    tok = d["access_token"]

    # 1 — the plant's own facts. Without these triage has no money and no
    #     deadline, and reports that rather than inventing them.
    if cfg["context"] and os.path.exists(cfg["context"]):
        with open(cfg["context"]) as f:
            ctx = json.load(f)
        ctx.pop("_comment", None)
        ctx.pop("factory_id", None)           # the tenant comes from the token
        st, r = call("/factory-setup/ingest", tok, "POST", ctx)
        print(f"  [{factory_id}] context: {r.get('loaded')} · "
              f"can_price={(r.get('triage_readiness') or {}).get('can_quantify_cost')}"
              if st == 200 else f"  [{factory_id}] context failed: {r}")

    # 2 — connect, and read the tag list from the source itself.
    call("/sources/connect", tok, "POST",
         {"source_id": cfg["source_id"], "type": "sse_stream", "endpoint": cfg["endpoint"]})
    st, disc = call("/sources/discover", tok, "POST",
                    {"type": "sse_stream", "endpoint": cfg["endpoint"]})
    if st != 200 or not disc.get("ok"):
        print(f"  [{factory_id}] discover failed: {disc.get('detail')}")
        return

    # 3 — map it. The LLM tier resolves the cryptic ISA tags (TT_101, VE_102)
    #     the free heuristics cannot.
    #
    #     Always asked for, and the backend decides: it is the API that knows
    #     whether Gemini is configured, and it already answers "not configured"
    #     by leaving fields unmapped rather than guessing. Gating this on the
    #     seeder's own environment meant a key present in the API's env — the
    #     normal case — still produced a half-mapped plant, because this script
    #     could not see it.
    st, prop = call("/normalization/propose", tok, "POST", {
        "source_id": cfg["source_id"], "sample_payload": disc["sample_payload"],
        "machine_id_field": disc["machine_id_field"],
        "use_llm": True,
        "field_units": disc["field_units"],
    })
    if st != 200:
        print(f"  [{factory_id}] propose failed: {prop}")
        return
    call("/normalization/confirm", tok, "POST", {"mapping": {
        "source_id": cfg["source_id"],
        "machine_id_strategy": prop["machine_id_strategy"],
        "machine_id_value": prop["machine_id_value"],
        "fields": prop["fields"], "unmapped": prop["unmapped"], "confirmed": True,
    }})
    s = prop["stats"]
    print(f"  [{factory_id}] mapped {s['mapped']}/{s['mapped'] + s['unmapped']} tags · "
          f"units {s.get('by_unit_status')}")

    # 4 — the plant's memory. After the mapping, necessarily: the history is in
    #     the plant's own tags and units, and watchers look baselines up by
    #     canonical signal.
    if cfg["history"] and os.path.exists(cfg["history"]):
        st, r = upload_history(cfg["history"], tok, cfg["source_id"])
        if st == 200:
            print(f"  [{factory_id}] learned {r['records_analyzed']} records → "
                  f"{len(r['signals_learned'])} signals: {', '.join(r['signals_learned'][:4])}")
        else:
            print(f"  [{factory_id}] history: {r.get('detail')}")

    # 5 — one monitor, if it isn't already there.
    m = cfg["monitor"]
    st, ex = call("/custom-agents/list", tok)
    agents = ex if isinstance(ex, list) else (ex.get("agents") or [])
    if m["name"] not in {a.get("name") for a in agents}:
        call("/custom-agents/create", tok, "POST", {
            "name": m["name"], "description": m["description"], "domain": m["domain"],
            "watch_signals": m["watch_signals"], "scope": {"type": "all"},
            "data_sources": [], "rules": m["rules"], "actions": [],
        })
    st, w = call("/stream-agents/", tok)
    print(f"  [{factory_id}] monitor '{m['name']}' · {w.get('count', 0)} watchers live")


def main() -> None:
    if not wait_for_api():
        print("commission_demo: the API never came up", file=sys.stderr)
        sys.exit(1)
    print("\nCommissioning both plants through the API:\n")
    for fid, cfg in PLANTS.items():
        commission(fid, cfg)
    print("\nReady → http://localhost:3000\n")
    for cfg in PLANTS.values():
        print(f"   {cfg['email']:28} / {cfg['password']}")
    if not os.getenv("GEMINI_API_KEY"):
        print("\n  No GEMINI_API_KEY set: the agents will use their deterministic rule")
        print("  fallback and say so on screen. Detection, unit conversion, learned")
        print("  baselines, governance and triage are unaffected.")


if __name__ == "__main__":
    main()
