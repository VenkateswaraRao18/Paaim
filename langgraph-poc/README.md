# langgraph-poc

A **proof of concept** that rebuilds PAAIM's orchestration pipeline on
**LangGraph** — the framework the professor asked for — demonstrating the three
things he named (agents + memory + tracing) plus native human-in-the-loop
approval.

It is **fully isolated**: separate folder, its own **Python 3.12** venv. The
working backend (Python 3.9) is untouched and unaffected.

## Why a POC and not a migration
The main backend runs on Python 3.9; LangGraph needs 3.10+. Rather than risk the
working system right before a review, this POC proves the architecture on 3.12.
The migration path is then: bump the backend to 3.12 → port the orchestrator
nodes (the logic already exists) → swap our hand-rolled loop for this graph.

## What it shows
| Professor's ask | How LangGraph delivers it here |
|---|---|
| **Agents on LangGraph** | each pipeline stage is a graph **node**; flow is **edges** (`enrich_context → run_agents → decide → finalize`) |
| **Memory** | `MemorySaver` **checkpointer** — full decision state is durably saved and **resumable** (keyed by `thread_id`) |
| **Human approval** | `interrupt_before=["finalize"]` — the graph **pauses for a person**, then resumes with their decision (PAAIM's approval gate, native) |
| **Tracing** | LangGraph integrates with **LangSmith** out of the box — set `LANGSMITH_API_KEY` and every node run streams to the dashboard |

The agent nodes use simple rules so the POC needs no API key; in the real system
those nodes call Gemini exactly as the 3.9 backend does today.

## Run
```bash
cd langgraph-poc
python3.12 -m venv venv && source venv/bin/activate   # (~/.local/bin/python3.12)
pip install -r requirements.txt
python run.py
```

## What you'll see
The event runs through the graph, **pauses at the approval gate with the
checkpoint saved**, a manager approves, and the graph **resumes from the
checkpoint** to finalize the decision — the same event→decision flow as the main
backend, now on LangGraph with built-in memory and human-in-the-loop.
