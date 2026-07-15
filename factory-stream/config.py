"""
factory-stream configuration — the simulated plant(s) PAAIM connects to.

Two plants live here, chosen with STREAM_PLANT. They exist to be as unlike each
other as two real customers are, because that is the only honest test of whether
PAAIM is a product or one plant's demo:

    cnc   — a machine shop. ISA tags (TT_101, VE_102), °C, bar, kW.
            Everything fails HIGH. Everything routes to maintenance.

    food  — a US dairy/beverage line. Descriptive SCADA tags with unit
            suffixes, °F, psi, grams, units/min. Two signals fail LOW — a
            pasteuriser losing hold pressure and a line slowing down are both
            faults. Routes to quality and production, not just maintenance.

Nothing about a plant lives in the generators any more: baselines, limits,
direction and units all come from the catalogue below. A generator that knows
°C is a generator that cannot simulate a plant using °F.

Each signal is one instrument:
    machine_id  — must match the machine ids ingested as factory context
    kind        — which physics model drives it (internal to this simulator)
    tag         — what THIS plant's SCADA calls it, and what the feed publishes.
                  PAAIM is expected to learn these through its mapping layer.
    label       — display text only; never used for routing
    unit        — what the instrument actually measures in, published on every
                  reading so PAAIM can reconcile it against its vocabulary
                  rather than assume the two already agree.
"""

import os

PORT = int(os.getenv("STREAM_PORT", "9100"))
HOST = os.getenv("STREAM_HOST", "0.0.0.0")

# How often a fresh reading is produced for every signal (seconds).
TICK_SECONDS = float(os.getenv("STREAM_TICK_SECONDS", "2.0"))

FACTORY_ID = os.getenv("STREAM_FACTORY_ID", "factory_001")

# Which plant this feed simulates: "cnc" | "food"
PLANT = os.getenv("STREAM_PLANT", "cnc").lower()


# ── Plant catalogues ────────────────────────────────────────────────────────
# (machine_id, kind, tag, label, unit, baseline, noise, warn, critical, higher_is_worse)
# Transcribed exactly from the generator classes these values used to live in.
# Note the press: hydraulic pressure fails LOW (a drop is a leak), so this plant
# already had one inverted signal before the food line existed.
_CNC = [
    ("robot_arm_01",   "temperature", "TT_101",    "Robot Arm 1 — Weld Temp",           "°C",    68.0,  1.6,  82.0,  90.0, True),
    ("robot_arm_01",   "vibration",   "VE_102",    "Robot Arm 1 — Vibration",           "mm/s",   2.8, 0.35,   4.5,   7.1, True),
    ("cnc_mill_01",    "vibration",   "VE_201",    "CNC Mill 1 — Vibration",            "mm/s",   2.8, 0.35,   4.5,   7.1, True),
    ("cnc_mill_01",    "temperature", "TT_205",    "CNC Mill 1 — Spindle Temp",         "°C",    68.0,  1.6,  82.0,  90.0, True),
    ("cnc_lathe_01",   "vibration",   "VE_301",    "CNC Lathe 1 — Vibration",           "mm/s",   2.8, 0.35,   4.5,   7.1, True),
    ("press_line_01",  "pressure",    "PT_HYD_01", "Press Line 1 — Hydraulic Pressure", "bar",    5.4, 0.18,   3.5,   2.2, False),
    ("cnc_cluster_03", "energy",      "JT_TOT_04", "CNC Cluster 3 — Power Draw",        "kW",   560.0, 22.0, 780.0, 880.0, True),
]

# Northfield Foods — a US HTST dairy line. Nothing here shares a naming
# convention, a unit, or a failure direction with the machine shop above.
_FOOD = [
    ("pasteuriser_01", "temperature", "PSTR1_PROD_TEMP_F",    "Pasteuriser 1 — Product Temp",       "°F",       165.0,  1.4, 172.0, 178.0, True),
    # Hold-tube pressure falling is the fault: product stops being held long
    # enough to be safe. LOWER is worse — the opposite of every CNC signal.
    ("pasteuriser_01", "pressure",    "PSTR1_HOLD_PRESS_PSI", "Pasteuriser 1 — Hold Tube Pressure", "psi",       45.0,  1.8,  36.0,  30.0, False),
    ("mixer_01",       "vibration",   "MIXR1_AGIT_VIB",       "Mixer 1 — Agitator Vibration",       "mm/s",       2.3, 0.35,   4.5,   7.1, True),
    ("mixer_02",       "vibration",   "MIXR2_AGIT_VIB",       "Mixer 2 — Agitator Vibration",       "mm/s",       2.0, 0.35,   4.5,   7.1, True),
    # Overfill is giveaway — money out of the door on every bottle.
    ("filler_01",      "temperature", "FILR1_NET_WT_G",       "Filler 1 — Net Fill Weight",         "g",        500.0,  2.2, 508.0, 514.0, True),
    ("filler_02",      "temperature", "FILR2_NET_WT_G",       "Filler 2 — Net Fill Weight",         "g",        500.0,  2.2, 508.0, 514.0, True),
    # A line slowing down is the fault. LOWER is worse.
    ("packer_01",      "energy",      "PACK1_LINE_SPD",       "Packer 1 — Line Speed",              "units/min", 118.0,  3.5, 100.0,  85.0, False),
    ("chiller_01",     "temperature", "CHIL1_ROOM_TEMP_F",    "Chiller 1 — Cold Room Temp",         "°F",        38.0,  0.8,  42.0,  45.0, True),
]

_PLANTS = {"cnc": _CNC, "food": _FOOD}

if PLANT not in _PLANTS:
    raise ValueError(f"STREAM_PLANT must be one of {sorted(_PLANTS)} — got '{PLANT}'")

SIGNALS = _PLANTS[PLANT]
