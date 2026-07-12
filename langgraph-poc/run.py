"""
Demo: run an event through the LangGraph pipeline, pause at the approval gate
(human-in-the-loop), then resume with the human's decision.

This is the same event → decision flow as the main PAAIM backend, expressed on
LangGraph with native memory (checkpointer) and a real interrupt for approval.
"""

from pipeline import build_pipeline

LINE = "─" * 60


def main():
    graph = build_pipeline()

    event = {
        "event_type": "maintenance",
        "machine_id": "robot_arm_01",
        "signal_name": "tool_wear_degradation",
        "signal_value": 84.0,
        "confidence": 0.94,
    }
    # thread_id ties all checkpoints for this decision together (= the memory key)
    config = {"configurable": {"thread_id": "decision-robot_arm_01-001"}}

    print(LINE)
    print("  PAAIM on LangGraph — event → decision (human-in-the-loop)")
    print(LINE)
    print(f"  EVENT: {event['signal_name']} = {event['signal_value']} on {event['machine_id']}\n")

    # 1) Run until the graph pauses before the approval gate.
    graph.invoke({"event": event}, config)
    snap = graph.get_state(config)
    s = snap.values
    print("  Pipeline ran: context → agents → decide, then PAUSED for approval.")
    print(f"    • Agents proposed   : {[a['action'] for a in s['agent_analyses']]}")
    print(f"    • Selected action   : {s['selected_action']}  (risk: {s['risk_level']})")
    print(f"    • Approval required : {s['approval_required']} → routed to {s['approver']}")
    print(f"    • Next node (paused): {snap.next}")
    print(f"    • Checkpoint saved  : memory holds the full state, resumable anytime\n")

    # 2) A human approves — inject the decision into the graph's memory.
    print(f"  👤 {s['approver']} reviews and APPROVES.\n")
    graph.update_state(config, {"approved": True})

    # 3) Resume from the checkpoint — finalize runs with the human's decision.
    graph.invoke(None, config)
    final = graph.get_state(config).values["decision"]

    print("  Resumed from checkpoint → final decision:")
    print(f"    • Action : {final['action']}")
    print(f"    • Risk   : {final['risk']}")
    print(f"    • Status : {final['status'].upper()} (by {final['approver']})")
    print(f"    • Context: {final['context']['customer']} order, "
          f"${final['context']['downtime_cost_per_hour']}/hr at stake")
    print(LINE)
    print("  ✓ Same pipeline as PAAIM — now on LangGraph with memory + human approval.")
    print(LINE)


if __name__ == "__main__":
    main()
