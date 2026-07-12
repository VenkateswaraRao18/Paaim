"""
Ask PAAIM — a conversational assistant grounded in the live factory state.

The chatbot answers operator/manager questions ("which orders are at risk?",
"what does 0x4F3 mean?", "what's the vibration baseline for cnc_mill_01?") using
Gemini, with a fresh snapshot of the factory injected on every turn so answers
are grounded in real data rather than made up.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import (
    get_db, MachineAssetModel, WorkOrderModel, CustomerOrderModel,
    NCRRecordModel, DecisionModel, FactoryKnowledgeModel,
)
from paaim.semantic.plc_codes import list_codes
from paaim.semantic.maintenance_logs import get_historian

router = APIRouter()


class ChatMessage(BaseModel):
    role: str            # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    factory_id: str = "factory_001"
    decision_id: Optional[str] = None   # when set, the bot is a co-pilot for THIS decision


async def _factory_snapshot(factory_id: str, db: AsyncSession) -> str:
    now = datetime.utcnow()
    lines: List[str] = []

    machines = (await db.execute(
        select(MachineAssetModel).where(MachineAssetModel.factory_id == factory_id))).scalars().all()
    if machines:
        running = sum(1 for m in machines if m.status == "running")
        fault = sum(1 for m in machines if m.status == "fault")
        lines.append(f"Machines: {len(machines)} total, {running} running, {fault} in fault.")

    wos = (await db.execute(select(WorkOrderModel).where(
        WorkOrderModel.factory_id == factory_id, WorkOrderModel.status == "in_progress"))).scalars().all()
    if wos:
        lines.append(f"Active work orders: {len(wos)} (" +
                     ", ".join(f"{w.id} on {w.machine_id}" for w in wos[:5]) + ").")

    cos = (await db.execute(select(CustomerOrderModel).where(
        CustomerOrderModel.factory_id == factory_id, CustomerOrderModel.status == "open"))).scalars().all()
    at_risk = [c for c in cos if (c.promised_delivery - now).total_seconds() / 3600 < 48]
    if cos:
        lines.append(f"Customer orders: {len(cos)} open, {len(at_risk)} at risk of missing deadline" +
                     (": " + ", ".join(f"{c.customer_name} ({c.id})" for c in at_risk[:3]) if at_risk else "") + ".")

    ncrs = (await db.execute(select(NCRRecordModel).where(
        NCRRecordModel.factory_id == factory_id, NCRRecordModel.status == "open"))).scalars().all()
    if ncrs:
        lines.append(f"Open quality issues (NCRs): {len(ncrs)}.")

    pending = (await db.execute(select(func.count()).select_from(DecisionModel).where(
        DecisionModel.factory_id == factory_id, DecisionModel.status == "recommended"))).scalar() or 0
    lines.append(f"Decisions awaiting human approval: {pending}.")

    # PLC codes the assistant can explain
    codes = list_codes()
    if codes:
        lines.append("Known machine codes: " +
                     "; ".join(f"{c['code']}={c['plain_meaning']}" for c in codes) + ".")

    # Learned baselines
    fk = (await db.execute(select(FactoryKnowledgeModel).where(
        FactoryKnowledgeModel.factory_id == factory_id).limit(1))).scalar_one_or_none()
    if fk and fk.profile:
        parts = []
        for mid, m in list((fk.profile.get("machines") or {}).items())[:4]:
            sig = ", ".join(f"{s} normal {v['normal_range'][0]}-{v['normal_range'][1]}"
                            for s, v in list((m.get("signals") or {}).items())[:2])
            mtbf = f", MTBF {m['mtbf_hours']}h" if m.get("mtbf_hours") else ""
            parts.append(f"{mid} ({sig}{mtbf})")
        if parts:
            lines.append("Learned baselines: " + "; ".join(parts) + ".")

    return "\n".join(f"- {l}" for l in lines) or "- No factory data seeded yet."


async def _decision_context(decision_id: str, db: AsyncSession) -> Tuple[str, Optional[str], Optional[str]]:
    """Build a context block for the decision the user is looking at, and return
    the machine/signal so we can retrieve matching tribal knowledge."""
    d = (await db.execute(
        select(DecisionModel).where(DecisionModel.id == decision_id))).scalar_one_or_none()
    if not d:
        return "", None, None

    ra = d.recommended_action or {}
    outcome = d.outcome or {}
    event = outcome.get("event") or {}
    layers = outcome.get("analysis_layers") or {}
    machine_id = event.get("machine_id")
    signal_name = event.get("signal_name")

    lines = [
        f"THE DECISION THE USER IS VIEWING ({decision_id}, status: {d.status}):",
        f"- What happened: {signal_name or 'event'} on {machine_id or 'a machine'}",
        f"- Recommended action: {ra.get('selected_action', 'unknown')} (risk: {ra.get('risk_level', 'n/a')})",
        f"- Needs approval from: {ra.get('approval_route', 'operator')}",
    ]
    # agent reasoning, if present
    analyses = layers.get("agent_analyses") or []
    reasons = [a.get("reasoning") for a in analyses if isinstance(a, dict) and a.get("reasoning")]
    if reasons:
        lines.append("- Agent findings: " + " | ".join(reasons[:3]))
    # red-team / risks
    rt = layers.get("red_team_reviews") or {}
    action_rt = rt.get(ra.get("selected_action")) if isinstance(rt, dict) else None
    if isinstance(action_rt, dict) and action_rt.get("risk_factors"):
        lines.append("- Risks flagged: " + "; ".join(action_rt["risk_factors"][:3]))

    return "\n".join(lines), machine_id, signal_name


def _tribal_knowledge(machine_id: Optional[str], signal_name: Optional[str], query: str) -> str:
    """Retrieve similar past fixes from maintenance history (RAG / keyword)."""
    if not (machine_id or signal_name or query):
        return ""
    try:
        hits = get_historian().search(machine_id or "", signal_name or "", query, limit=3)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = ["PAST SIMILAR FIXES (from maintenance history — use to answer 'has this happened before?'):"]
    for h in hits:
        lines.append(f"- {h.get('raw_note', '')} → fixed by: {h.get('resolution', 'n/a')} "
                     f"({h.get('downtime_min', '?')} min, {h.get('date', '')})")
    return "\n".join(lines)


@router.post("")
@router.post("/")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    from paaim.agents.base import _get_gemini
    client, available = _get_gemini()
    if not (available and client):
        return {"reply": "The assistant needs the Gemini API key configured to answer."}

    snapshot = await _factory_snapshot(req.factory_id, db)
    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")

    # Co-pilot context: the specific decision the user is on + matching tribal knowledge
    decision_block, machine_id, signal_name = "", None, None
    if req.decision_id:
        decision_block, machine_id, signal_name = await _decision_context(req.decision_id, db)
    tribal_block = _tribal_knowledge(machine_id, signal_name, last_user)

    history = "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in req.messages[-8:]
    )

    extra = "\n\n".join(b for b in (decision_block, tribal_block) if b)
    focus = ("You are helping with the specific decision above — answer about IT first "
             "(why this action, why not alternatives, what it costs), and cite the past fixes "
             "when asked whether this happened before.\n") if req.decision_id else ""

    prompt = f"""You are "PAAIM Assistant", a friendly, concise factory-operations co-pilot.
You help operators and managers understand what's happening and what to do.

CURRENT FACTORY STATE (factory {req.factory_id}, live):
{snapshot}
{extra}

Guidelines:
- {focus}Answer from the context above when relevant; if you don't have the data, say so plainly.
- Explain machine codes and jargon in plain language for a junior operator.
- Be concise (2-5 sentences). Friendly, confident tone. No markdown headers.

Conversation:
{history}
Assistant:"""

    try:
        resp = client.generate_content(prompt)
        return {"reply": (resp.text or "").strip()}
    except Exception as e:
        return {"reply": f"Sorry, I hit an error answering that ({e})."}
