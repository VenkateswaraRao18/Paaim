"""Deterministic incident prioritisation.

Safety-first with a loss-minimising tiebreak — the philosophy a real ops
manager would defend. Four legible inputs (financial exposure, delivery
urgency, safety risk, confidence) combine into a 0–100 score, which maps to an
L1/L2/L3 tier. Every result carries its own drivers so the tier is never a
black box.

Pure and side-effect free: callers resolve the raw facts (from the stored
decision, the cost model, and the customer order) and hand them in.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

# ── tunables (the plant's philosophy lives here) ──────────────────────────────
EXPOSURE_CAP_USD = 150_000.0      # exposure at/above this counts as "maxed"
URGENCY_HORIZON_H = 48.0          # a deadline this far out has ~zero urgency
W_EXPOSURE = 0.40
W_URGENCY = 0.30
W_SAFETY = 0.30
L1_SCORE = 65
L2_SCORE = 35
CONF_FLOOR = 0.30                 # confidence de-rates the score, never below this
LOW_CONF = 0.40                   # below this, cannot be L1 unless safety-critical

_SAFETY = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.15}
# nominal downtime (hours) when impact estimates are missing — keyed by risk
_RISK_DOWNTIME_H = {"critical": 4.0, "high": 2.0, "medium": 1.0, "low": 0.25}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class PriorityResult:
    level: str                    # "L1" | "L2" | "L3"
    score: int                    # 0–100
    rationale: str                # one-line human summary
    drivers: List[str]            # ranked contributing factors
    factors: Dict[str, Any]       # raw numbers, for the detail view / audit

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_downtime_hours(
    impact_estimates: Optional[Dict[str, Any]],
    selected_action: str,
    risk_level: str,
) -> float:
    """Downtime (hours) for the selected action, with a risk-based fallback."""
    est = (impact_estimates or {}).get(selected_action) or {}
    dh = est.get("downtime_hours")
    if isinstance(dh, (int, float)) and dh > 0:
        return float(dh)
    return _RISK_DOWNTIME_H.get((risk_level or "").lower(), 1.0)


def score_incident(
    *,
    risk_level: str,
    downtime_hours: float,
    cost_per_hour: Optional[float],   # None = the plant has no cost model yet
    failure_multiplier: float = 5.0,
    confidence: Optional[float] = None,
    hours_to_due: Optional[float] = None,
    penalty_usd: float = 0.0,
    customer_name: Optional[str] = None,
    order_id: Optional[str] = None,
) -> PriorityResult:
    """Score one incident into an L1/L2/L3 tier with explainable drivers.

    hours_to_due: hours until the tied customer order is due (None = no order,
    negative/zero = past due). penalty_usd is added to the financial exposure.
    """
    risk = (risk_level or "low").lower()

    # ── financial exposure ────────────────────────────────────────────────────
    # `cost_per_hour=None` means the plant has not told us what an hour of
    # downtime costs. It is not zero and it is not a guess: a default here put
    # "$12K at risk" in front of an operator as grounds to stop a line, on a
    # site PAAIM knew nothing about. An unknown must read as unknown.
    #
    # A late-delivery penalty is real money from a real order, so it counts even
    # when the hourly cost does not.
    cost_known = cost_per_hour is not None and cost_per_hour > 0
    penalty = max(0.0, penalty_usd)
    if cost_known:
        exposure_usd: Optional[float] = (
            max(0.0, downtime_hours) * cost_per_hour * max(1.0, failure_multiplier) + penalty
        )
    elif penalty > 0:
        exposure_usd = penalty          # partial, and honest about being partial
    else:
        exposure_usd = None             # nothing known — say so, do not invent
    exposure_norm = 0.0 if exposure_usd is None else _clamp(exposure_usd / EXPOSURE_CAP_USD, 0.0, 1.0)

    # ── delivery urgency ──────────────────────────────────────────────────────
    past_due = hours_to_due is not None and hours_to_due <= 0
    if past_due:
        urgency = 1.0
    elif hours_to_due is None:
        urgency = 0.15  # no linked order — a mild floor, not zero
    else:
        near = _clamp((URGENCY_HORIZON_H - hours_to_due) / URGENCY_HORIZON_H, 0.0, 1.0)
        urgency = near * near  # steepen toward the deadline

    # ── safety ────────────────────────────────────────────────────────────────
    safety = _SAFETY.get(risk, 0.15)

    # ── confidence de-rating ──────────────────────────────────────────────────
    conf = 0.8 if confidence is None else _clamp(float(confidence), 0.0, 1.0)
    conf_factor = _clamp(conf, CONF_FLOOR, 1.0)

    if exposure_usd is None:
        # Score on what is known, renormalised over the remaining factors.
        # Treating an unknown exposure as a zero contribution would dock every
        # incident 40 points on a plant with no cost model — pushing genuine
        # safety incidents into L3 and making the whole queue look calm.
        total_w = W_URGENCY + W_SAFETY
        raw = 100.0 * ((W_URGENCY / total_w) * urgency + (W_SAFETY / total_w) * safety)
    else:
        raw = 100.0 * (W_EXPOSURE * exposure_norm + W_URGENCY * urgency + W_SAFETY * safety)
    score = int(round(raw * conf_factor))

    # ── tier (safety-first overrides) ─────────────────────────────────────────
    safety_critical = risk == "critical"
    if safety_critical or past_due or score >= L1_SCORE:
        level = "L1"
    elif score >= L2_SCORE:
        level = "L2"
    else:
        level = "L3"
    # low-confidence guard: don't let a noisy blip claim L1 on score alone
    if level == "L1" and conf < LOW_CONF and not (safety_critical or past_due):
        level = "L2"

    drivers = _drivers(
        exposure_usd=exposure_usd, exposure_norm=exposure_norm,
        past_due=past_due, hours_to_due=hours_to_due,
        risk=risk, safety=safety, conf=conf,
        customer_name=customer_name, order_id=order_id,
        cost_known=cost_known,
    )
    rationale = " · ".join(drivers[:3]) if drivers else "Low impact, no delivery pressure"

    return PriorityResult(
        level=level,
        score=score,
        rationale=rationale,
        drivers=drivers,
        factors={
            # None, not 0 — a reader must not be able to mistake "we don't know"
            # for "it's free".
            "exposure_usd": None if exposure_usd is None else round(exposure_usd),
            "cost_model_configured": cost_known,
            "exposure_basis": ("downtime + penalty" if cost_known
                               else "late-delivery penalty only" if exposure_usd is not None
                               else "unknown — no cost model for this factory"),
            "hours_to_due": None if hours_to_due is None else round(hours_to_due, 1),
            "safety": safety,
            "confidence": round(conf, 2),
            "past_due": past_due,
            "order_id": order_id,
            "customer_name": customer_name,
        },
    )


def _money(n: float) -> str:
    if n >= 1000:
        return f"${n / 1000:.0f}K"
    return f"${n:.0f}"


def _drivers(*, exposure_usd, exposure_norm, past_due, hours_to_due,
             risk, safety, conf, customer_name, order_id, cost_known=True) -> List[str]:
    """Rank the factors that pushed this incident up, as human phrases."""
    scored: List[tuple] = []  # (weight, phrase)

    if risk == "critical":
        scored.append((1.0, "restart is safety-critical"))
    elif risk == "high":
        scored.append((0.7, "high safety risk"))

    if exposure_usd is None:
        # Surfaced as a driver, not hidden: the tier really was decided without
        # any financial input, and the operator is entitled to know that the
        # money side of this judgement is missing rather than merely small.
        scored.append((0.5, "cost impact unknown — no cost model configured"))
    elif exposure_usd >= 1000:
        at_risk = f"{_money(exposure_usd)} at risk"
        scored.append((exposure_norm, at_risk if cost_known else f"{at_risk} (late penalty only)"))

    if past_due:
        who = f"{customer_name} " if customer_name else ""
        scored.append((1.0, f"{who}order past due"))
    elif hours_to_due is not None and hours_to_due <= URGENCY_HORIZON_H:
        who = f"{customer_name} " if customer_name else ""
        when = f"{hours_to_due:.0f}h" if hours_to_due >= 1 else "under 1h"
        scored.append((_clamp((URGENCY_HORIZON_H - hours_to_due) / URGENCY_HORIZON_H, 0, 1),
                       f"{who}order due in {when}"))

    if conf < LOW_CONF:
        scored.append((0.2, "low-confidence signal"))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [phrase for _, phrase in scored]
