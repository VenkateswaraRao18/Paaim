# PAAIM: Policy-Aware Agentic Intelligence Manager

A policy-aware, bounded-autonomy manufacturing decision orchestration layer that coordinates AI agents across safety, quality, maintenance, production, and energy domains.

## Overview

PAAIM solves a critical manufacturing problem: when multiple events happen simultaneously (safety hazard + quality defect + machine failure + order delay), existing AI systems provide fragmented alerts. PAAIM acts as a trusted decision orchestration layer that:

- **Coordinates** diverse agents (safety, quality, maintenance, production, energy, compliance)
- **Reasons** about factory policies and priorities
- **Simulates** alternatives before recommending actions
- **Governs** decisions with human approval gates and auditability
- **Extends** through user-defined custom agents (no code required)

## Key Features

- **7-Layer Architecture**: From events to approved actions
- **Multi-Agent Coordination**: Specialist agents + super-agent orchestration
- **Policy Engine**: Factory-specific policies (Industrial Constitution)
- **Decision Twin**: Simulate impact before acting
- **Red-Team Challenge**: Verify recommendations for safety and feasibility
- **Evidence Trail**: Complete audit record of decisions
- **Custom Agent Framework**: Define new agents via config, not code

## Project Status

**Phase 0: Foundation Setup** (Current)
- Monorepo structure
- Database schema
- Core abstractions
- Docker Compose environment

**Timeline**: 
- Phase 0: Week 1
- Phase 1 (Prototype 0.1): Weeks 2-7
- Phase 2 (Research Validation): Weeks 8-13
- Phase 3 (Executive Demo): Weeks 14-16
- Phase 4 (Pilot Readiness): Weeks 17-28

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Pydantic |
| **Frontend** | Next.js 14+, React 18+, shadcn/ui, Zustand |
| **Database** | PostgreSQL, Alembic migrations |
| **Events** | Redis Pub/Sub |
| **AI** | Anthropic Claude API, Ollama (optional) |
| **Testing** | pytest, Jest, Playwright |
| **Deployment** | Docker Compose, Kubernetes-ready |

## Project Structure

```
PAAIM/
├── backend/                    # Python FastAPI backend
│   ├── paaim/
│   │   ├── agents/            # Agent implementations
│   │   ├── policy/            # Policy engine
│   │   ├── decision_twin/     # Simulation & impact
│   │   ├── governance/        # Approval gate, red-team
│   │   ├── knowledge_model/   # Factory schema
│   │   ├── event_input/       # Event simulator
│   │   ├── models.py          # Pydantic models
│   │   ├── database.py        # Database setup
│   │   └── main.py            # FastAPI app
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic/               # Migrations
├── frontend/                   # Next.js dashboard
│   ├── app/
│   ├── components/
│   └── package.json
├── docker-compose.yml         # Local dev environment
├── docs/                      # Research papers, guides
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### Local Development

```bash
# Clone and navigate
cd /Users/venky/Desktop/projects/PAAIM

# Start services (PostgreSQL, Redis)
docker-compose up -d

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
alembic upgrade head

# Run backend tests
pytest

# Frontend setup
cd ../frontend
npm install
npm run dev

# Dashboard available at http://localhost:3000
# API available at http://localhost:8000
```

### Run Prototype Demo
```bash
cd backend
python -m paaim.event_input.simulator
# Generates synthetic incidents → processes through PAAIM pipeline → outputs decisions
```

## Research & Publication

### First Paper
**Title**: "PAAIM: A Policy-Aware Multi-Agent Decision Orchestration Framework for Bounded-Autonomy Manufacturing"

**Target**: IEEE Transactions on Industrial Informatics, Journal of Manufacturing Systems

**Contributions**:
1. Problem formulation: Multi-event incident orchestration under policy constraints
2. Architecture: Policy engine + multi-agent reasoning + Decision Twin + governance
3. Custom Agent Framework: Extensible orchestration without code changes
4. Experimental validation: Comparison vs. baselines on 20-30 incident scenarios

## Startup Vision

**Category**: Policy-Aware Industrial Decision Orchestration for Bounded-Autonomy Manufacturing

**One-Line Pitch**: "PAAIM turns manufacturing alert overload into coordinated, policy-compliant action by connecting fragmented AI systems into one governed orchestration layer."

**MVP Target**: 2-3 beta pilots (automotive or food) proving ROI on incident response

**TAM Expansion**: Custom agents enable all manufacturing verticals; real connectors enable all factory sizes

## Success Criteria

- ✅ Research: Journal publication + reproducible experiments
- ✅ Product: Working demo with measurable ROI
- ✅ Startup: 2-3 beta pilots + investor pitch ready
- ✅ Extensibility: Custom agents addable without code

## Core Design Principles

1. **Safety First** — Never bypass certified safety systems
2. **Human-Governed Autonomy** — Every action bounded by explicit policy
3. **Evidence Before Action** — Every recommendation shows signals, confidence, assumptions
4. **Policy as Product** — Industrial Constitution is a core asset
5. **Simulation Before Action** — Test impact via Decision Twin
6. **Audit by Default** — Complete record of events, decisions, approvals, outcomes
7. **Integration Friendly** — Sits above existing systems, requires no replacement
8. **Measurable Value** — Every demo quantifies operational impact

## Contributing

This is an active research + product development project. See CLAUDE.md for detailed development guidelines.

## Roadmap

- **Phase 0** (Week 1): Foundation—monorepo, database, core abstractions
- **Phase 1** (Weeks 2-7): Prototype 0.1—event simulator, agents, policy engine, Decision Twin, dashboard
- **Phase 2** (Weeks 8-13): Research Validation—experiments, baselines, paper writing
- **Phase 3** (Weeks 14-16): Executive Demo—ROI calculator, pitch deck, pilot template
- **Phase 4** (Weeks 17-28): Pilot Readiness—real connectors, security, multi-tenancy, documentation

## Contact

**Research & Product Lead**: venkateswararao18

---

**PAAIM**: Building the decision orchestration layer for intelligent manufacturing.
