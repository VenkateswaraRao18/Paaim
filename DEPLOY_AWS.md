# Put PAAIM on the internet (one EC2 box)

Goal: a URL you can send. `http://<public-ip>:3000`, sign in, done. No Docker on
anyone else's machine.

This runs PAAIM as a **single instance** — which is exactly what it is designed
for today (see the note at the bottom). Good for a demo, a pilot, or one plant.

---

## 1. Launch the instance

AWS Console → EC2 → **Launch instance**:

| Setting | Value |
|---|---|
| Name | `paaim-demo` |
| AMI | **Ubuntu Server 24.04 LTS** |
| Instance type | **t3.medium** (2 vCPU, 4 GB) — the 4 GB matters; `next build` OOMs on 1 GB |
| Key pair | create or pick one (you need it to SSH in) |
| Storage | 20 GB gp3 |

**Security group — inbound rules.** Add these three, and set the source to
**My IP** (or your professor's IP), not `0.0.0.0/0`. The auth is real, but do
not expose the simulated plants to the whole internet.

| Type | Port | Source |
|---|---|---|
| SSH | 22 | My IP |
| Custom TCP | 3000 | My IP (the web app) |
| Custom TCP | 8000 | My IP (the API — the browser calls it directly) |

Launch. Note the **Public IPv4 address** — call it `PUBLIC_IP` below.

---

## 2. Connect and install Docker

```bash
ssh -i your-key.pem ubuntu@PUBLIC_IP

# Docker + compose plugin
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu
newgrp docker            # apply the group without logging out
```

---

## 3. Clone and run

```bash
git clone <your-repo-url> paaim
cd paaim

# Optional but recommended — real reasoning instead of the rule fallback:
echo "GEMINI_API_KEY=your-key-here" > .env
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env

# The one line that makes it work from a remote browser.
# PAAIM_HOST is the box's public IP — what the browser will call.
PAAIM_HOST=PUBLIC_IP docker compose up -d --build
```

First build is 5–10 min on a t3.medium. Watch it commission:

```bash
docker compose logs -f api      # wait for: "Ready → http://localhost:3000"
```

(That line says `localhost` because it is printed from inside the container —
your URL is the public IP.)

---

## 4. Share it

```
http://PUBLIC_IP:3000
```

Sign in as either plant:

| Plant | Email | Password |
|---|---|---|
| Northfield Foods (dairy) | `ops@northfield.example` | `northfield123` |
| Precision Parts Co (CNC) | `ops@precision.example` | `precision123` |

---

## Running costs

- **t3.medium ≈ $0.04/hour** (~$30/month if left on).
- **Stop it when you are not demoing** — EC2 → Instances → Stop. You then pay
  only for the 20 GB disk (~$1.60/month). Start it again when you need it; the
  public IP changes on stop/start unless you attach an Elastic IP (free while
  attached to a running instance).

## Everyday commands

```bash
docker compose ps                    # what is running
docker compose logs -f api           # API logs
docker compose restart               # after a config change (no rebuild)
PAAIM_HOST=PUBLIC_IP docker compose up -d --build   # after a git pull
docker compose down                  # stop (keeps the data volume)
docker compose down -v               # stop and wipe to a blank PAAIM
```

## Honest limits of this setup

- **HTTP, not HTTPS.** Fine for a demo; a browser may warn. For a real URL, put
  it behind a domain + an nginx/Caddy TLS proxy, or an AWS ALB with an ACM cert.
- **One instance only.** Watchers, pollers and the incident deduper hold state
  in the process, so a second replica would double every incident and split the
  dedupe window. That is fine here and is the deliberate design for one box. The
  work to scale out — dedupe to Redis/ElastiCache, elect a single watcher owner,
  move tenant state and the bus off local disk into Postgres/MSK — is real and
  is the line between this demo and a multi-plant production service.
- **Data lives on the box's disk** (SQLite + the tenant files in the Docker
  volume). Snapshot the volume if the state matters; `down -v` erases it.
