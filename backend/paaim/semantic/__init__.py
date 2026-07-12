"""
Semantic Disconnect layer.

Bridges the gap between cryptic machine output (PLC error codes, raw sensor
registers) and a human-readable action plan a junior operator can follow —
the core use case the project is now focused on.

Flow:
    cryptic code / raw signal
        → Telemetry interpretation  (what it means)
        → Log Historian             (what fixed it before — from messy logs)
        → SOP Dispatcher            (a plain step-by-step action plan)
"""

from paaim.semantic.plc_codes import lookup_code, list_codes
from paaim.semantic.maintenance_logs import get_historian
from paaim.semantic.sop_dispatcher import dispatch_sop

__all__ = ["lookup_code", "list_codes", "get_historian", "dispatch_sop"]
