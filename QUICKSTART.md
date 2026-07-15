# Run PAAIM on a laptop

One dependency: **Docker Desktop**. No Python, no Node, no database to install.

```bash
git clone <repo> && cd PAAIM
cp .env.example .env         # optional — add a Gemini key for real AI reasoning
docker compose up --build    # first run ~3-4 min; after that, seconds
```

Then open **http://localhost:3000**.

Sign in as either plant — the point of the demo is that they share a deployment
and nothing else:

| Plant | Sign in | Password |
|---|---|---|
| Northfield Foods (dairy, °F/psi) | `ops@northfield.example` | `northfield123` |
| Precision Parts Co (CNC, °C/bar) | `ops@precision.example` | `precision123` |

Everything is commissioned for you on first boot: two tenants, their own signal
vocabularies, their own plants connected and mapped, Northfield's 30-day history
learned, and a monitor each.

## What to look at

1. **Live Feed** — watchers judging live readings. Northfield's chiller reads
   ~3.5 °C: the plant sends 38 °F, and the mapping converts it.
2. **Data Sources** — the mapping table. `°F → C converted`, `psi → bar converted`.
3. **Simulate fault** on Live Feed — watch a real incident go through the
   pipeline. It takes ~45s: that is the LLM reasoning, and it is the honest number.
4. **Operations** → click the incident → the 8-step reasoning timeline.
5. **Sign in as the other plant.** Different vocabulary, different machines,
   different incidents. Neither can see the other.

## Without a Gemini key

Everything runs. The agents use their deterministic rule fallback and label
themselves as such — the reasoning is just not a model's. Detection, unit
reconciliation, learned baselines, governance and triage are identical.

## Ports

| | |
|---|---|
| 3000 | web |
| 8000 | API (`/docs` for the OpenAPI browser) |
| 9100 | the simulated dairy |
| 9101 | the simulated machine shop |

## Reset to a blank PAAIM

```bash
docker compose down -v && docker compose up --build
```

`-v` drops the volume, which is where SQLite and the tenant state live.

## Troubleshooting

**Ports already taken** — something else is on 3000/8000. Stop it, or edit the
left-hand side of the `ports:` mappings in `docker-compose.yml`.

**"Backend unreachable" in the UI** — the API takes a few seconds longer than
the web app on first boot. Give it a moment; `docker compose logs api` will say.

**No incidents after Simulate fault** — a watcher only raises on `critical`, not
`warning`, and once per fault episode (rising edge + cooldown). Check Live Feed:
the card goes amber, then red, then the incident appears ~45s later.
