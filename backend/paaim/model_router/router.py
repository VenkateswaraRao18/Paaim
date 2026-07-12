"""
Model Router

Decides which AI model (or rule engine) handles each agent task based on:
  - Event risk level
  - Signal confidence
  - Task complexity
  - Factory operator configuration

Tiers (cheapest → most capable):
  RULES   — zero API cost, deterministic, <1ms
  FAST    — Gemini Flash / smallest local model, low cost, ~500ms
  SMART   — Gemini Pro / mid-size local model, medium cost, ~1500ms
  BEST    — Best available (Claude Sonnet / GPT-4o / Gemini Ultra), highest cost

Why this matters:
  A simple low-confidence maintenance alert does not need the same model as
  a critical safety decision that could shut down a production line. Routing
  saves API cost and latency without sacrificing quality where it counts.
"""

import os
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ── Tiers ─────────────────────────────────────────────────────────────────────

class ModelTier(str, Enum):
    RULES = "rules"    # no LLM — deterministic rule engine only
    FAST  = "fast"     # cheap + fast LLM (Gemini Flash / llama3)
    SMART = "smart"    # mid-tier LLM (Gemini Pro / mistral-medium)
    BEST  = "best"     # best available (Claude Sonnet / GPT-4o)


@dataclass
class ModelDecision:
    tier: ModelTier
    model_id: str               # actual model identifier string
    provider: str               # "gemini" | "ollama" | "anthropic" | "openai"
    reason: str                 # human-readable explanation
    estimated_cost_usd: float   # per 1K tokens, approximate


# ── Default model catalogue ───────────────────────────────────────────────────
# Override any of these via environment variables or the factory config YAML.

_DEFAULTS: Dict[ModelTier, ModelDecision] = {
    ModelTier.RULES: ModelDecision(
        tier=ModelTier.RULES,
        model_id="rules_engine_v1",
        provider="internal",
        reason="Deterministic rule-based analysis — no API cost",
        estimated_cost_usd=0.0,
    ),
    ModelTier.FAST: ModelDecision(
        tier=ModelTier.FAST,
        model_id=os.getenv("PAAIM_FAST_MODEL", "gemini-2.0-flash"),
        provider=os.getenv("PAAIM_FAST_PROVIDER", "gemini"),
        reason="Fast inference for routine analysis",
        estimated_cost_usd=0.000075,  # ~$0.075 / 1M tokens
    ),
    ModelTier.SMART: ModelDecision(
        tier=ModelTier.SMART,
        model_id=os.getenv("PAAIM_SMART_MODEL", "gemini-1.5-pro"),
        provider=os.getenv("PAAIM_SMART_PROVIDER", "gemini"),
        reason="Mid-tier reasoning for complex multi-factor events",
        estimated_cost_usd=0.00125,   # ~$1.25 / 1M tokens
    ),
    ModelTier.BEST: ModelDecision(
        tier=ModelTier.BEST,
        model_id=os.getenv("PAAIM_BEST_MODEL", "claude-sonnet-4-6"),
        provider=os.getenv("PAAIM_BEST_PROVIDER", "anthropic"),
        reason="Best available for critical safety/compliance decisions",
        estimated_cost_usd=0.003,     # ~$3.00 / 1M tokens
    ),
}


# ── Routing rules ─────────────────────────────────────────────────────────────

class ModelRouter:
    """
    Stateless router — call select() before each agent invocation.

    Configuration can be overridden per factory via factory_config dict
    (loaded from the industry pack YAML or the database FactoryModel.config).
    """

    def __init__(self, factory_config: Optional[Dict[str, Any]] = None):
        self._config = factory_config or {}
        self._catalogue = dict(_DEFAULTS)

        # Allow factory-level overrides: {"model_router": {"fast": "ollama/llama3", ...}}
        router_cfg = self._config.get("model_router", {})
        for tier_name, model_id in router_cfg.items():
            try:
                tier = ModelTier(tier_name)
                if tier in self._catalogue:
                    old = self._catalogue[tier]
                    provider = "ollama" if "ollama" in model_id.lower() else old.provider
                    self._catalogue[tier] = ModelDecision(
                        tier=tier,
                        model_id=model_id,
                        provider=provider,
                        reason=f"Factory override: {model_id}",
                        estimated_cost_usd=0.0 if provider == "ollama" else old.estimated_cost_usd,
                    )
            except ValueError:
                logger.warning(f"Unknown model tier in factory config: {tier_name}")

    def select(
        self,
        event_type: str,
        risk_level: Optional[str],
        confidence: float,
        has_memory_pattern: bool = False,
        has_active_customer_order: bool = False,
        force_tier: Optional[ModelTier] = None,
    ) -> ModelDecision:
        """
        Select the appropriate model tier for an agent task.

        Decision logic (in priority order):
          1. force_tier — explicit override (used by custom agents)
          2. BEST    — safety events with critical/high risk
          3. BEST    — any critical risk with active customer order at risk
          4. SMART   — high risk OR escalating memory pattern OR active customer order
          5. FAST    — medium risk, normal confidence
          6. RULES   — low risk, low confidence (not worth an API call)
        """
        if force_tier is not None:
            decision = self._catalogue[force_tier]
            logger.debug(f"Model forced to {force_tier}: {decision.model_id}")
            return decision

        risk = (risk_level or "low").lower()
        is_safety = event_type.lower() == "safety"

        # Critical safety — always use best
        if is_safety and risk in ("critical", "high"):
            return self._pick(ModelTier.BEST, "Safety event with high/critical risk")

        # Critical risk anywhere — best if customer order is at stake
        if risk == "critical":
            if has_active_customer_order:
                return self._pick(ModelTier.BEST, "Critical risk with active customer order")
            return self._pick(ModelTier.SMART, "Critical risk — no active order")

        # High risk or escalating pattern — smart
        if risk == "high":
            return self._pick(ModelTier.SMART, "High risk event")
        if has_memory_pattern and risk == "medium":
            return self._pick(ModelTier.SMART, "Medium risk with repeated pattern in memory")
        if has_active_customer_order and risk == "medium":
            return self._pick(ModelTier.SMART, "Medium risk with active customer order deadline")

        # Medium risk — fast LLM
        if risk == "medium" and confidence >= 0.7:
            return self._pick(ModelTier.FAST, "Medium risk, sufficient confidence")

        # Low confidence or low risk — rule engine
        if confidence < 0.7 or risk == "low":
            return self._pick(ModelTier.RULES, "Low risk or low confidence — rules only")

        # Default
        return self._pick(ModelTier.FAST, "Default fast tier")

    def _pick(self, tier: ModelTier, reason: str) -> ModelDecision:
        decision = self._catalogue[tier]
        logger.debug(f"Model selected: {decision.model_id} ({tier}) — {reason}")
        return ModelDecision(
            tier=decision.tier,
            model_id=decision.model_id,
            provider=decision.provider,
            reason=reason,
            estimated_cost_usd=decision.estimated_cost_usd,
        )

    def get_catalogue(self) -> Dict[str, Dict[str, Any]]:
        """Return current model catalogue — for the frontend config UI."""
        return {
            tier.value: {
                "model_id": md.model_id,
                "provider": md.provider,
                "reason": md.reason,
                "estimated_cost_usd_per_1k_tokens": md.estimated_cost_usd,
            }
            for tier, md in self._catalogue.items()
        }


# ── Singleton (default factory config) ───────────────────────────────────────

_router: Optional[ModelRouter] = None


def get_router(factory_config: Optional[Dict[str, Any]] = None) -> ModelRouter:
    global _router
    if _router is None or factory_config is not None:
        _router = ModelRouter(factory_config)
    return _router
