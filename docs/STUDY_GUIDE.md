# PAAIM — Complete Study Guide
### Everything you need to understand and present this project (domain + product)

> **How to use this doc:** Read Part A to sound fluent about the *industry*. Read
> Part B to explain the *product*. Use Part C the night before a presentation.
> The 🎤 **"How to say it"** callouts are your talking points; the ⚠️ **honesty**
> notes keep you from overclaiming in front of experts.

---

# PART A — DOMAIN KNOWLEDGE (the manufacturing world)

## A1. The core problem
Factories are **drowning in data but starved of decisions.** Three pains:

1. **Alert overload** — thousands of sensor alarms/day. A raw number (`vibration = 7.2`) has *data* but no *context* and no *action*. Important alerts drown in noise ("alarm fatigue").
2. **The skills/labor gap** — senior engineers who understood the machines are **retiring in a wave**. Junior operators see a cryptic code (`Error 0x4F3`) and freeze. The knowledge is walking out the door.
3. **The cost of every minute** — a stopped line costs **thousands/hour**; an *unplanned* failure costs **~5× a planned one**, plus scrap and customer late-penalties.

🎤 **The one-liner:** *"Factories don't have a data problem — they have a decision problem: turning a flood of raw machine signals into the right action, fast, by the right person — especially now that the experts are retiring."*

## A2. The systems & vocabulary (know these cold)

| Term | What it is | Analogy |
|---|---|---|
| **PLC** (Programmable Logic Controller) | The rugged industrial computer that runs a machine; outputs cryptic codes/registers | The machine's "brainstem" |
| **SCADA** | System that supervises/collects data from many PLCs across the plant | The "control room dashboard" |
| **MES** (Manufacturing Execution System) | Tracks work orders, production, what's being made right now | The "shop-floor to-do list" |
| **ERP** | Business system: customer orders, inventory, finance | The "company's back office" |
| **CMMS** | Maintenance management: work orders, PM schedules, asset history | The "maintenance logbook" |
| **Sensor / telemetry** | Live measurements: temp, vibration, pressure, torque, RPM, power | The machine's "vital signs" |
| **Actuator** | Something that *acts* (stops a line, changes a setpoint) | The "hands" |
| **Setpoint** | Target value the machine aims for (e.g. temp 68°C) | A thermostat setting |

🎤 **Say it:** *"Machines talk through PLCs, SCADA aggregates their signals, MES knows what's being produced, ERP knows the customer orders, CMMS holds maintenance history. PAAIM's job is to fuse all of these into one decision."*

## A3. The metrics that run a factory

| Metric | Meaning | Why it matters |
|---|---|---|
| **OEE** (Overall Equipment Effectiveness) | Availability × Performance × Quality | The single "how well is this line running" number (world-class ≈ 85%) |
| **MTBF** (Mean Time Between Failures) | Avg run time between breakdowns | Higher = more reliable |
| **MTTR** (Mean Time To Repair) | Avg time to fix a failure | Lower = faster recovery |
| **Scrap rate** | % of parts thrown away | Direct waste/cost |
| **First-pass yield** | % made right the first time | Quality efficiency |
| **Throughput** | Units produced per shift | Output |
| **Downtime cost/hr** | $ lost per hour a line is stopped | The urgency multiplier |

🎤 **Say it:** *"If a plant manager remembers one number, it's OEE. PAAIM's decisions are designed to protect OEE and minimize downtime cost."*

## A4. Quality & maintenance concepts

- **Preventive maintenance (PM):** fix on a *schedule* (every 500 hrs). Simple but wasteful.
- **Predictive maintenance (PdM):** fix based on *condition* (vibration trend says a bearing is dying). Smarter — fix *just before* failure. **This is the sweet spot AI enables.**
- **NCR** (Non-Conformance Report): a logged quality defect.
- **CAPA** (Corrective And Preventive Action): the fix + prevention for a recurring defect.
- **AOI** (Automated Optical Inspection): cameras that check parts for defects — the industrial version of PAAIM's Vision Agent.
- **HACCP / IATF 16949 / ISO 9001:** compliance standards (food safety, automotive quality, general quality) — factories are *legally* bound to them, which is why **governance and audit trails matter**.

🎤 **Say it:** *"The industry is shifting from preventive (calendar-based) to predictive (condition-based) maintenance. PAAIM sits right in that shift — and adds the governance that regulated industries require."*

## A5. Why "agentic AI in manufacturing" is hot *right now*
- **Agentic AI** = AI that doesn't just answer, it *reasons, plans, and acts* across steps, often as multiple cooperating agents.
- Industry reports (Manufacturing Dive, etc.) say agentic AI is **scaling in manufacturing but blocked by infrastructure gaps** — mainly **fragmented data** (telemetry, vision, and text logs all live in separate silos) and **LLM reasoning reliability**.
- The **labor shortage** makes it urgent: AI has to capture the retiring experts' knowledge.

🎤 **Say it:** *"PAAIM is aimed exactly at the gap the industry named: it unifies fragmented factory data and wraps LLM reasoning in governance so it's trustworthy."*

---

# PART B — PRODUCT KNOWLEDGE (what PAAIM is)

## B1. The one-liner & elevator pitch
**PAAIM = Policy-Aware Agentic Intelligence Manager.**

🎤 **Elevator pitch (30 sec):**
> *"PAAIM turns the flood of factory alerts into governed decisions. When a machine signals a problem, a team of AI agents reads the full business context — the order, the customer, the cost, the history — recommends the best action with trade-offs, checks it against safety policy, simulates the cost, and routes it to the right human to approve. And it translates cryptic machine codes into plain action plans a junior operator can follow. Everything is logged for audit."*

## B2. The core idea — two big concepts

**(1) "Alert → Governed Decision."** Without PAAIM, a factory is an *alarm system*. With it, it's a *decision control tower*. The magic is adding **context + governance** to a raw signal.

**(2) The "Semantic Disconnect."** The gap between what the **machine says** (`0x4F3`) and what a **human should do** ("check the coolant filter, here's the 6-step plan"). PAAIM bridges it — this is the answer to the labor/skills gap.

🎤 **Say it:** *"Two ideas: we turn alerts into governed decisions, and we translate machine-language into human action."*

## B3. The 7-layer decision pipeline + the Factory Context Graph

Every event flows through a pipeline (this is PAAIM's spine):

```
1. Event          a signal arrives (sensor, code, or camera)
2. Context        enrich it with the Factory Context Graph
3. Memory         has this happened before? (patterns)
4. Agents         specialist AI agents analyze & recommend
5. Policy         check against the "Industrial Constitution" (allowed actions)
6. Decision Twin  simulate the cost/downtime/quality impact
7. Red-Team       a second AI questions the recommendation (safety double-check)
   → Approval     route to the right human (operator/supervisor/manager)
   → Audit        log every step for compliance
```

**The Factory Context Graph** is the heart. It links every event to **10 data domains**: machine, work order, customer order, product/quality specs, material batch, maintenance history, NCR/CAPA, approval matrix, cost model, policy.

🎤 **Say it:** *"The Context Graph turns a sensor reading into a *situation*. Without it PAAIM is an alarm; with it, it's a decision. That's the professor's own idea, and it's the core."*

⚠️ **Honesty:** the pipeline is real and runs end-to-end; the factory data is realistic synthetic seed data (plus the real AI4I research dataset).

## B4. The agents

**Original 5 specialist "monitors":** Safety, Quality, Maintenance, Production, Energy — each an LLM agent (Gemini 2.5 Flash) that reads the same shared context.

**The new modality pipeline** (the professor's evolved architecture):
- **Telemetry Agent** — interprets sensor streams / PLC codes → failure mode.
- **Vision Agent** — multimodal defect detection from a camera image (Gemini).
- **Log Historian Agent** — retrieves "what fixed this before" from messy maintenance logs.
- **SOP Dispatcher Agent** — fuses it all into a plain step-by-step action plan.

🎤 **Say it:** *"Agents are specialists. The newest ones map to data types — telemetry, vision, text logs — and all feed a dispatcher that writes the human action plan."*

⚠️ **Honesty:** agents are powered by **Google Gemini**, not a self-trained model. That's a *strength* (fast, multimodal, no training) — say so confidently.

## B5. Governance — the trust layer (this is what makes it *enterprise*)

- **Policy Engine ("Industrial Constitution"):** a fixed catalogue of ~11 allowed actions with approval levels. Agents can *only* recommend from it — no rogue actions.
- **Decision Twin:** simulates each action's cost, downtime, scrap, OEE impact — so decisions are **cost-aware**, not just technically correct.
- **Red-Team:** a second AI that challenges the recommendation and suggests safer alternatives (a built-in "second opinion").
- **Approval Gate:** routes by risk to the right human — low risk auto-approves, critical goes to a safety officer. **Human-in-the-loop.**
- **Audit Trail:** every step (event → each agent → policy → decision → approval) is recorded — essential for regulated industries.

🎤 **Say it:** *"This governance layer is why a factory would actually trust AI to touch a line. The AI proposes; policy constrains; a human approves; everything is logged."*

## B6. Data & reliability (the infrastructure the industry says is missing)

- **Event Bus:** a durable, replayable message backbone (at-least-once delivery, dead-letter queue). **Kafka-ready** — flip a config flag for production. This solves "reliable data feeds."
- **Streaming ingestion:** a standalone `factory-stream` service simulates live sensors; agents *connect* to it and raise decisions on anomalies — real-time.
- **Learning from history (Factory Memory):** upload past data → the system computes each machine's **normal ranges, MTBF, and recurring issues** → future decisions judge readings against the machine's *own* history.

🎤 **Say it:** *"We built the reliable data backbone the industry reports say is the #1 blocker — durable streaming, plus a memory that learns each factory."*

## B7. The Semantic Disconnect & Vision (the current focus)

- **Operator Assist:** type a cryptic code (`0x4F3`) → get **(a)** plain meaning, **(b)** what fixed it before (from maintenance logs), **(c)** a safety-first step-by-step SOP with escalation rules. **This directly attacks the labor gap.**
- **Vision Agent:** upload a part photo → Gemini multimodal detects defects (crack/scratch/corrosion) + disposition (accept/rework/scrap). **No CV model trained** — pure multimodal LLM.

⚠️ **Honesty:** PLC codes, maintenance logs, and test images are *representative/synthetic*; the engines are real and dataset-agnostic — the real MaintNet (logs) and Future Factories (vision) datasets drop into the same interfaces.

## B8. The tech stack (one line each)
- **Backend:** Python, FastAPI, SQLAlchemy (async), SQLite (dev).
- **AI:** Google Gemini 2.5 Flash (text + multimodal).
- **Frontend:** Next.js 14, React, TailwindCSS, React Query.
- **Streaming:** custom durable Event Bus (Kafka-ready), Server-Sent Events.
- **Explored:** LangGraph (agent orchestration POC), MCP (Model Context Protocol server).

---

# PART C — PRESENTING TO STAKEHOLDERS

## C1. The business / ROI story (lead with money, not tech)
Stakeholders fund **outcomes**, not architectures. Frame every feature as ROI:

| Feature | Business value |
|---|---|
| Alert → decision | Less alarm fatigue; catch the costly failure before it happens |
| Semantic Disconnect | Junior operators act like veterans → mitigates the retirement crisis |
| Decision Twin (cost) | Every decision is a dollars-and-cents call, not a guess |
| Predictive + streaming | Turn unplanned (5×-cost) failures into planned fixes |
| Governance + audit | Safe enough to trust AI on a real line; passes compliance |
| Learning from history | Gets smarter the longer it runs at *your* plant |

🎤 **The money slide:** *"An unplanned failure costs ~5× a planned one. If PAAIM converts even a handful of unplanned stops per month into scheduled fixes, it pays for itself — before counting the labor-gap savings."*

## C2. The demo script (5 minutes, in order)
1. **Operator Assist** — type `0x4F3` → plain meaning + past fixes + action plan. *(The labor-gap wow.)*
2. **Vision** — upload `01_good_part.jpg` (accept), then `02_crack.jpg` (crack → scrap). *(Multimodal wow.)*
3. **Live Feed** — "Connect all monitors" → "Simulate fault" → a live decision appears. *(Real-time wow.)*
4. **Operations → open a decision** — show "Options for the approver" with cost trade-offs + "if no action." *(Governance wow.)*
5. **Factory Memory** — it learned baselines/MTBF from history. *(Learning wow.)*

## C3. Tough questions — and your answers
- **"Is the data real?"** → *"The AI4I predictive-maintenance dataset is real, peer-reviewed research. The rest is realistic synthetic seed data; every engine is dataset-agnostic and takes real factory exports."*
- **"Did you train the AI?"** → *"No — we use Google Gemini, including its multimodal vision. That's deliberate: fast, capable, no training pipeline, and it keeps all agents consistent."*
- **"Can it run a real line today?"** → *"It's a working prototype. The governance, streaming, and audit are production-shaped; connecting to real PLCs/cameras and hardening is the next phase."*
- **"How is this different from existing SCADA/MES?"** → *"Those *show* data. PAAIM *decides* — it fuses their data, reasons over it, and produces a governed action with a human in the loop."*
- **"What about hallucination / trust?"** → *"That's exactly why the policy engine, red-team second opinion, human approval, and audit trail exist. The AI proposes; it never acts unchecked."*
- **"Real-time camera?"** → *"Vision works on demand today; live is a frame-sampling extension of our streaming architecture. Line-speed uses a fast edge CV model to screen frames, then the LLM to reason — the standard industry pattern."*

---

# GLOSSARY (quick reference)
- **Agentic AI** — AI that reasons, plans, and acts over multiple steps, often as cooperating agents.
- **PLC / SCADA / MES / ERP / CMMS** — see A2.
- **OEE / MTBF / MTTR** — see A3.
- **PdM** — predictive maintenance (condition-based).
- **NCR / CAPA** — quality defect report / corrective+preventive action.
- **AOI** — automated optical (camera) inspection.
- **Event Bus** — durable message backbone (our Kafka-ready streaming layer).
- **Multimodal** — an AI that handles multiple input types (text + image).
- **Semantic Disconnect** — the gap between machine-language and human action; PAAIM's core focus.
- **Factory Context Graph** — the shared map linking an event to all 10 factory data domains.
- **Industrial Constitution** — the policy catalogue of allowed actions.
- **Decision Twin** — the cost/impact simulator.
- **SOP** — Standard Operating Procedure (the action plan).

---

*Last: pair this with a live run of the app (all 3 services up) and rehearse the C2 demo twice. You'll be fluent.*
