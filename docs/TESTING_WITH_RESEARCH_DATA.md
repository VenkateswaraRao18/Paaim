# Testing PAAIM with Real Research Data

This guide explains how to validate PAAIM against a real, peer-reviewed
industrial dataset instead of the built-in synthetic scenarios — the test your
professor asked for.

## Dataset: AI4I 2020 Predictive Maintenance (UCI #601)

- **Source:** UCI Machine Learning Repository, dataset #601
  <https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset>
- **Paper:** S. Matzka, *"Explainable Artificial Intelligence for Predictive
  Maintenance Applications,"* 2020 Third International Conference on AI for
  Industries (AI4I).
- **License:** CC BY 4.0 (free for research and education).
- **Size:** 10,000 rows of milling-machine telemetry.
- **Why this one:** it is the only widely-cited public PdM dataset that encodes
  **five independent failure modes** in one file, so a single run exercises the
  Maintenance, Quality, Production and Energy agents, the policy engine, the
  decision twin and the approval gate — exactly what PAAIM is built to
  coordinate. (Bearing/CWRU and SECOM are *more* physically real but exercise
  only one agent on raw signals.)

### Columns

| Column | Meaning |
|---|---|
| `Type` | Product quality variant — L / M / H |
| `Air temperature [K]`, `Process temperature [K]` | Thermal readings |
| `Rotational speed [rpm]`, `Torque [Nm]` | Drive parameters |
| `Tool wear [min]` | Cumulative tool wear |
| `Machine failure` + `TWF/HDF/PWF/OSF/RNF` | Failure label + which of 5 modes |

### How PAAIM maps each row → events

The adapter (`backend/data_adapters/ai4i2020.py`) uses the **documented physics
thresholds from the paper** — not arbitrary cutoffs — so the events are faithful:

| Mode | Physics (from paper) | PAAIM signal | Event type |
|---|---|---|---|
| **TWF** Tool Wear | wear 200–240 min | `tool_wear_degradation` | maintenance |
| **HDF** Heat Dissipation | (proc−air) < 8.6 K & speed < 1380 rpm | `heat_dissipation_loss` | maintenance |
| **PWF** Power | power = torque·ω ∉ [3500, 9000] W | `power_envelope_breach` | energy |
| **OSF** Overstrain | wear·torque > 11000/12000/13000 (L/M/H) | `mechanical_overstrain` | production |
| **RNF** Random | 0.1% random | `unexplained_quality_fault` | quality |

`signal_value` is the raw physical reading; `confidence` is graded by how far
into the danger zone the reading is. The machine `Type` (L/M/H) is mapped onto
the seeded factory machines, so dataset events also flow through the **Factory
Context Layer** (real work orders, customer deadlines, cost model).

## Running the test

### 1. Get the data
Download `ai4i2020.csv` from the UCI link above (or Kaggle mirror) and place it at:

```
backend/data_adapters/ai4i2020.csv
```

A 12-row **sample** (`ai4i2020_sample.csv`, one row per failure mode) ships in
the repo so you can prove the pipeline before downloading the full file.

### 2. Run it through the pipeline

```bash
cd backend && source venv/bin/activate

# prove it on the bundled sample
python run_dataset.py --file data_adapters/ai4i2020_sample.csv --limit 0 --clear

# full dataset, capped at 150 decisions (each row → real Gemini agent calls)
python run_dataset.py --clear

# only labelled failures (no warning-band rows)
python run_dataset.py --failures-only

# no cap — runs the whole file (slow: thousands of LLM calls)
python run_dataset.py --all
```

Or trigger from the API (appears live in the UI):

```bash
curl -X POST "http://localhost:8000/api/events/dataset/ingest?sample=true&limit=50"
curl     "http://localhost:8000/api/events/dataset/info"
```

### 3. Review the results
Open the frontend and check:
- **Operations → Decisions** — each dataset row's governed decision + approval routing
- **Audit Trail** — full evidence trail per decision (agent reasoning, policy, approval)
- **Analytics** — event distribution, approval rate, agent performance over the real data

## What "good" looks like
- Tool-wear / heat / overstrain rows → `schedule_maintenance`, `inspect_root_cause`,
  `escalate_critical` or `stop_line`, routed to the correct human by risk.
- The agents cite the real thresholds in their reasoning (Gemini 2.5 Flash).
- Auto-approve for low-risk, human approval for critical — demonstrating governance.

## Notes / honesty for the writeup
- AI4I 2020 is **industry-modelled synthetic** data (high realism, published
  thresholds), not raw factory sensor logs. For *physically real* sensor data,
  the same adapter pattern extends to **CWRU Bearing** (vibration) or **SECOM**
  (semiconductor) — those need an FFT/feature step and map mainly to one agent.
- Agents are constrained to the 11 actions in the Industrial Constitution, so
  every recommendation is policy-valid and auditable.
