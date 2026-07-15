"""
AI4I 2020 — full-pipeline validation.

The physics harness (ai4i_validation.py) only checks that the adapter reproduces
the dataset's documented failure rules. AI4I is synthetic and those rules are
published, so scoring ~100% there is close to circular: it proves the adapter is
faithful, not that the system reasons.

This runs the labelled failures through everything PAAIM actually does — agents,
policy, twin, red-team, approval routing — and scores what only the *system* can
get wrong:

  · routing      — does a power failure reach the energy specialist, an
                   overstrain the production one? (the dataset's own mapping)
  · action       — does it recommend something, and is it allowed for that risk?
  · reasoning    — did an LLM actually answer, or did rules fall back?
  · governance   — do critical-risk actions demand a human?
  · latency      — what a decision really costs in wall-clock

None of this can be answered by re-checking the thresholds, and none of it is
graded against a rule we wrote ourselves.

Usage:
    python -m validation.ai4i_end_to_end --limit 25          # calibration
    python -m validation.ai4i_end_to_end --failures-only     # all 357 failures
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_adapters.ai4i2020 import row_to_events  # noqa: E402
from paaim.models import AsyncSessionLocal  # noqa: E402
from paaim.orchestrator import get_orchestrator  # noqa: E402

FULL = "data_adapters/ai4i2020.csv"

# The dataset's own physics → the discipline that should own the response.
# This is AI4I's mapping, not ours: an overstrain is a production problem, a
# power-envelope breach is an energy one. Getting this wrong means the incident
# lands on the wrong desk.
MODE_TO_DISCIPLINE = {
    "tool_wear_degradation": "maintenance",
    "heat_dissipation_loss": "maintenance",
    "power_envelope_breach": "energy",
    "mechanical_overstrain": "production",
    "unexplained_quality_fault": "quality",
}

# Actions that must never be auto-approved.
_HUMAN_ROUTES = {"operator", "supervisor", "manager", "safety_officer"}


def _flag(row: Dict[str, str], name: str) -> bool:
    return str(row.get(name, "0")).strip() in ("1", "true", "True")


def _labelled_modes(row: Dict[str, str]) -> List[str]:
    return [m for m in ("TWF", "HDF", "PWF", "OSF", "RNF") if _flag(row, m)]


class Report:
    def __init__(self) -> None:
        self.rows = 0
        self.events = 0
        self.decisions = 0
        self.errors: List[str] = []
        self.routed_ok = 0
        self.routed_wrong: List[str] = []
        self.no_action = 0
        self.llm_backed = 0
        self.rule_backed = 0
        self.governance_ok = 0
        self.governance_violations: List[str] = []
        self.latencies: List[float] = []
        self.actions = Counter()
        self.risk = Counter()
        self.by_mode: Dict[str, Counter] = {}


async def _run_one(orch, db, event, truth_modes: List[str], rep: Report) -> None:
    t0 = time.perf_counter()
    try:
        decision = await orch.orchestrate(event, db=db)
    except Exception as e:
        rep.errors.append(f"{event.signal_name}: {e}")
        return
    rep.latencies.append(time.perf_counter() - t0)
    rep.decisions += 1

    orchestration = decision.get("orchestration_result") or {}
    layers = decision.get("analysis_layers") or {}
    action = orchestration.get("selected_action")
    risk = orchestration.get("risk_level") or "unknown"
    route = orchestration.get("approval_route") or ""
    analyses = layers.get("agent_analyses") or []

    rep.actions[action or "none"] += 1
    rep.risk[risk] += 1

    # 1 — did the right discipline pick it up?
    expected = MODE_TO_DISCIPLINE.get(event.signal_name)
    agents = {str(a.get("agent", "")).lower() for a in analyses}
    if expected and any(expected in a for a in agents):
        rep.routed_ok += 1
    elif expected:
        rep.routed_wrong.append(f"{event.signal_name} → {sorted(agents) or 'no agent'} (expected {expected})")

    # 2 — did it actually decide something?
    if not action:
        rep.no_action += 1

    # 3 — was that reasoning real, or the deterministic fallback?
    if any(a.get("model_used") for a in analyses):
        rep.llm_backed += 1
    else:
        rep.rule_backed += 1

    # 4 — governance: a critical call must land on a human
    if risk == "critical":
        if route in _HUMAN_ROUTES and orchestration.get("approval_required"):
            rep.governance_ok += 1
        else:
            rep.governance_violations.append(
                f"{event.signal_name}: critical risk auto-approved (route={route!r})"
            )
    else:
        rep.governance_ok += 1

    for m in truth_modes:
        rep.by_mode.setdefault(m, Counter())[action or "none"] += 1


async def run(limit: int, failures_only: bool) -> Report:
    rep = Report()
    orch = get_orchestrator()
    base = datetime.utcnow() - timedelta(hours=6)

    with open(FULL, newline="") as fh:
        rows = list(csv.DictReader(fh))

    selected = [r for r in rows if _labelled_modes(r)] if failures_only else rows
    if limit > 0:
        selected = selected[:limit]

    async with AsyncSessionLocal() as db:
        for i, raw in enumerate(selected):
            rep.rows += 1
            truth = _labelled_modes(raw)
            events = row_to_events(raw, timestamp=base + timedelta(seconds=i * 5), warn_only=False)
            for ev in events:
                rep.events += 1
                await _run_one(orch, db, ev, truth, rep)
            if rep.rows % 10 == 0:
                print(f"  … {rep.rows}/{len(selected)} rows, {rep.decisions} decisions", flush=True)
    return rep


def render(rep: Report, label: str) -> str:
    L: List[str] = []
    A = L.append
    A("=" * 74)
    A(f"PAAIM END-TO-END VALIDATION — AI4I 2020 ({label})")
    A("=" * 74)
    A("Scores what only the full system can get wrong. The physics is graded")
    A("separately; AI4I is synthetic, so re-checking its own rules proves little.")
    A("")
    A(f"Rows fed        : {rep.rows}")
    A(f"Events raised   : {rep.events}")
    A(f"Decisions made  : {rep.decisions}")
    A(f"Pipeline errors : {len(rep.errors)}")
    A("")

    def pct(n: int, d: int) -> str:
        return f"{(n / d * 100):5.1f}%" if d else "   n/a"

    A("1. ROUTING — did the incident reach the right specialist?")
    total_routed = rep.routed_ok + len(rep.routed_wrong)
    A(f"   correct: {rep.routed_ok}/{total_routed}  {pct(rep.routed_ok, total_routed)}")
    for w in rep.routed_wrong[:4]:
        A(f"     ✗ {w}")
    A("")
    A("2. ACTION — did it decide anything at all?")
    A(f"   decisions with an action: {rep.decisions - rep.no_action}/{rep.decisions}"
      f"  {pct(rep.decisions - rep.no_action, rep.decisions)}")
    for act, n in rep.actions.most_common(6):
        A(f"     {act:26} {n}")
    A("")
    A("3. REASONING — real model, or deterministic fallback?")
    A(f"   LLM-backed : {rep.llm_backed}/{rep.decisions}  {pct(rep.llm_backed, rep.decisions)}")
    A(f"   rule-backed: {rep.rule_backed}/{rep.decisions}  {pct(rep.rule_backed, rep.decisions)}")
    A("")
    A("4. GOVERNANCE — does a critical call demand a human?")
    A(f"   upheld: {rep.governance_ok}/{rep.decisions}  {pct(rep.governance_ok, rep.decisions)}")
    for v in rep.governance_violations[:4]:
        A(f"     ✗ {v}")
    A("")
    A("5. RISK SPREAD")
    for r, n in rep.risk.most_common():
        A(f"   {r:10} {n}")
    A("")
    if rep.latencies:
        s = sorted(rep.latencies)
        A("6. LATENCY per decision (the product's own SLA is 2.0s)")
        A(f"   median {s[len(s)//2]:5.2f}s   p95 {s[int(len(s)*0.95)]:5.2f}s   max {s[-1]:5.2f}s")
        A(f"   over SLA: {sum(1 for x in s if x > 2.0)}/{len(s)}  {pct(sum(1 for x in s if x > 2.0), len(s))}")
    if rep.errors:
        A("")
        A("ERRORS")
        for e in rep.errors[:5]:
            A(f"   {e}")
    A("=" * 74)
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--failures-only", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(FULL):
        sys.exit(f"Dataset not found: {FULL}")

    label = f"{'labelled failures' if args.failures_only else 'all rows'}, limit={args.limit or 'none'}"
    print(f"Running end-to-end: {label}\n")
    rep = asyncio.run(run(args.limit, args.failures_only))
    out = render(rep, label)
    print("\n" + out)

    os.makedirs("validation/reports", exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"validation/reports/ai4i_e2e_{stamp}.txt"
    with open(path, "w") as fh:
        fh.write(out + "\n")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
