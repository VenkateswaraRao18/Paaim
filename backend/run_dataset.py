"""
Run a real industrial research dataset through the full PAAIM pipeline.

Each qualifying dataset row becomes one or more PAAIM events, which are pushed
through the complete 7-layer orchestration (Context → Memory → Agents → Policy →
Decision Twin → Red-Team → Approval → Audit). Events, decisions and audit
entries are persisted exactly like a live event, so they appear on the
Dashboard, Analytics and Audit Trail pages.

Usage:
    cd backend && source venv/bin/activate

    # default: AI4I 2020, anomaly/warning rows only, capped at 150 decisions
    python run_dataset.py

    # options
    python run_dataset.py --file data_adapters/ai4i2020.csv --limit 150
    python run_dataset.py --failures-only          # only labelled failures
    python run_dataset.py --all                     # no cap (slow: many LLM calls)
    python run_dataset.py --clear                   # wipe prior events/decisions first

Place the CSV at backend/data_adapters/ai4i2020.csv
(download: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
"""

import argparse
import asyncio
import csv
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./paaim_dev.db")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from paaim.models import engine, Base, EventModel, DecisionModel
from paaim.orchestrator import get_orchestrator
from paaim.api.events import persist_decision
from data_adapters.ai4i2020 import row_to_events, summarise_mapping

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _ensure_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _clear(session: AsyncSession):
    for t in ("audit_logs", "decisions", "events"):
        await session.execute(text(f"DELETE FROM {t}"))
    await session.commit()
    print("  Cleared prior events / decisions / audit logs.")


async def run(args):
    await _ensure_tables()

    if not os.path.exists(args.file):
        print(f"\n  ✗ Dataset file not found: {args.file}")
        print("    Download the AI4I 2020 CSV and place it there:")
        print("    https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset\n")
        sys.exit(1)

    mapping = summarise_mapping()
    print("=" * 64)
    print(f"  PAAIM — Dataset ingestion: {mapping['dataset']}")
    print("=" * 64)

    orchestrator = get_orchestrator()
    warn_only = not args.failures_only

    # Spread synthetic timestamps over the last 24h so the timeline looks live.
    base_ts = datetime.utcnow() - timedelta(hours=24)

    rows_read = 0
    events_made = 0
    decisions_made = 0
    mode_counter: Counter = Counter()
    risk_counter: Counter = Counter()
    auto_vs_human: Counter = Counter()

    async with AsyncSessionLocal() as session:
        if args.clear:
            await _clear(session)

        with open(args.file, newline="") as fh:
            reader = csv.DictReader(fh)
            total = None
            for i, raw in enumerate(reader):
                rows_read += 1
                ts = base_ts + timedelta(seconds=i * 8)
                events = row_to_events(raw, factory_id=args.factory,
                                       timestamp=ts, warn_only=warn_only)
                for event in events:
                    if decisions_made >= args.limit and args.limit > 0:
                        total = "limit"
                        break

                    decision = await orchestrator.orchestrate(event, db=session)
                    persist_decision(session, decision, event)
                    orch = decision.get("orchestration_result", {})
                    approval_required = orch.get("approval_required", True)

                    events_made += 1
                    decisions_made += 1
                    mode_counter[event.signal_name] += 1
                    risk_counter[orch.get("risk_level", "unknown")] += 1
                    auto_vs_human["auto" if not approval_required else "human"] += 1

                    if decisions_made % 20 == 0:
                        await session.commit()
                        print(f"  … {decisions_made} decisions ({rows_read} rows read)")

                if total == "limit":
                    break

        await session.commit()

    # ── Report ──────────────────────────────────────────────────────────────
    print("\n" + "-" * 64)
    print(f"  Rows read           : {rows_read:,}")
    print(f"  Events generated    : {events_made:,}")
    print(f"  Decisions persisted : {decisions_made:,}")
    print(f"  Mode               : {'labelled failures only' if args.failures_only else 'failures + warning bands'}")
    print("\n  Failure-mode breakdown:")
    for sig, n in mode_counter.most_common():
        print(f"    {sig:28} {n:4}")
    print("\n  Risk levels:")
    for r, n in risk_counter.most_common():
        print(f"    {r:12} {n:4}")
    print("\n  Approval routing:")
    for k, n in auto_vs_human.most_common():
        label = "auto-approved" if k == "auto" else "needs human approval"
        print(f"    {label:24} {n:4}")
    print("-" * 64)
    print("  ✓ Done. Open the Dashboard → Decisions tab and the Audit Trail to review.")
    print("=" * 64 + "\n")


def main():
    p = argparse.ArgumentParser(description="Run an industrial dataset through PAAIM.")
    p.add_argument("--file", default="data_adapters/ai4i2020.csv", help="CSV path")
    p.add_argument("--factory", default="factory_001")
    p.add_argument("--limit", type=int, default=150,
                   help="max decisions (0 = no cap). LLM calls make large runs slow.")
    p.add_argument("--failures-only", action="store_true",
                   help="only emit events for labelled failures (not warning bands)")
    p.add_argument("--all", action="store_true", help="alias for --limit 0")
    p.add_argument("--clear", action="store_true",
                   help="wipe prior events/decisions/audit before running")
    args = p.parse_args()
    if args.all:
        args.limit = 0
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
