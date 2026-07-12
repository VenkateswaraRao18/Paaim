"""
Observability & Tracing

Wraps every pipeline layer with LangSmith tracing when LANGSMITH_API_KEY is set.
Falls back to a no-op decorator when the key is absent — zero runtime impact,
no errors, no config required for local dev.

Usage:
    from paaim.observability.tracing import trace, trace_agent

    @trace("policy_engine")
    def evaluate(self, ctx): ...

    @trace_agent("safety_agent")
    async def analyze(self, event_data): ...

Set these env vars to enable LangSmith:
    LANGSMITH_API_KEY=lsv2_...
    LANGSMITH_PROJECT=paaim-production   (optional, defaults to "paaim")
    LANGSMITH_ENDPOINT=https://api.smith.langchain.com  (optional)
"""

import os
import logging
import functools
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── LangSmith setup ───────────────────────────────────────────────────────────

_ENABLED = False
_traceable = None

def _setup():
    global _ENABLED, _traceable
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        return

    try:
        from langsmith import traceable as _ls_traceable
        import langsmith

        client = langsmith.Client(
            api_key=api_key,
            api_url=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        )
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGSMITH_PROJECT", "paaim"))

        _traceable = _ls_traceable
        _ENABLED = True
        logger.info(
            f"LangSmith tracing enabled — project: {os.environ['LANGCHAIN_PROJECT']}"
        )
    except ImportError:
        logger.warning("langsmith not installed — tracing disabled")
    except Exception as e:
        logger.warning(f"LangSmith setup failed: {e} — tracing disabled")

_setup()


# ── Public decorators ─────────────────────────────────────────────────────────

def trace(run_name: str, run_type: str = "chain"):
    """
    Decorator for synchronous pipeline layers.

    Wraps with LangSmith @traceable when enabled, otherwise is a no-op.
    Always records wall-clock latency to the function's __paaim_latency_ms__
    attribute for internal use.
    """
    def decorator(fn: Callable) -> Callable:
        if _ENABLED and _traceable is not None:
            traced = _traceable(name=run_name, run_type=run_type)(fn)
        else:
            traced = fn

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = traced(*args, **kwargs)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.debug(f"[trace] {run_name} completed in {ms}ms")
            return result

        return wrapper
    return decorator


def trace_async(run_name: str, run_type: str = "chain"):
    """
    Decorator for async pipeline layers (agents, context service).
    """
    def decorator(fn: Callable) -> Callable:
        if _ENABLED and _traceable is not None:
            traced = _traceable(name=run_name, run_type=run_type)(fn)
        else:
            traced = fn

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = await traced(*args, **kwargs)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.debug(f"[trace] {run_name} completed in {ms}ms")
            return result

        return wrapper
    return decorator


def trace_agent(agent_name: str):
    """Shorthand for tracing agent.analyze() calls as LLM runs."""
    return trace_async(run_name=agent_name, run_type="llm")


def trace_pipeline(pipeline_name: str):
    """Shorthand for tracing the full orchestration pipeline."""
    return trace_async(run_name=pipeline_name, run_type="chain")


# ── Run metadata helper ───────────────────────────────────────────────────────

def get_tracing_status() -> dict:
    return {
        "enabled": _ENABLED,
        "project": os.environ.get("LANGCHAIN_PROJECT", "paaim") if _ENABLED else None,
        "endpoint": os.environ.get("LANGSMITH_ENDPOINT") if _ENABLED else None,
    }
