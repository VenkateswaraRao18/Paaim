"""
factory-stream configuration.

The signal catalogue maps onto the machines PAAIM already knows about
(robot_arm_01, cnc_mill_01, ...), so streamed readings line up with the
Factory Context Layer once an agent ingests them.
"""

import os

PORT = int(os.getenv("STREAM_PORT", "9100"))
HOST = os.getenv("STREAM_HOST", "0.0.0.0")

# How often a fresh reading is produced for every signal (seconds).
TICK_SECONDS = float(os.getenv("STREAM_TICK_SECONDS", "2.0"))

# Factory the readings belong to (matches PAAIM's seeded factory).
FACTORY_ID = os.getenv("STREAM_FACTORY_ID", "factory_001")

# ── Signal catalogue ────────────────────────────────────────────────────────
# Each entry: machine_id, signal kind, and the generator parameters.
# `kind` selects which generator class is used.
SIGNALS = [
    # machine_id        kind           label
    ("robot_arm_01",    "temperature", "Robot Arm 1 — Weld Temp"),
    ("robot_arm_01",    "vibration",   "Robot Arm 1 — Vibration"),
    ("cnc_mill_01",     "vibration",   "CNC Mill 1 — Vibration"),
    ("cnc_mill_01",     "temperature", "CNC Mill 1 — Spindle Temp"),
    ("cnc_lathe_01",    "vibration",   "CNC Lathe 1 — Vibration"),
    ("press_line_01",   "pressure",    "Press Line 1 — Hydraulic Pressure"),
    ("cnc_cluster_03",  "energy",      "CNC Cluster 3 — Power Draw"),
]
