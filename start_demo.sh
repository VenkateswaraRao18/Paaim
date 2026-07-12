#!/bin/bash
# PAAIM Demo Startup Script
# Usage: ./start_demo.sh [--seed]
# --seed  wipes and re-seeds the database with fresh demo data

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "  ██████╗  █████╗  █████╗ ██╗███╗   ███╗"
echo "  ██╔══██╗██╔══██╗██╔══██╗██║████╗ ████║"
echo "  ██████╔╝███████║███████║██║██╔████╔██║"
echo "  ██╔═══╝ ██╔══██║██╔══██║██║██║╚██╔╝██║"
echo "  ██║     ██║  ██║██║  ██║██║██║ ╚═╝ ██║"
echo "  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝"
echo -e "${NC}"
echo "  Policy-Aware Agentic Intelligence Manager"
echo "  Phase 1 Demo · Factory 001 · Austin TX"
echo ""

cd "$(dirname "$0")"

# ── Backend ───────────────────────────────────────────────────────────────────

echo -e "${YELLOW}[1/4] Setting up backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# Install deps silently if needed
pip install -q -r requirements.txt

# Seed database
if [[ "$1" == "--seed" ]] || [ ! -f "paaim_dev.db" ]; then
  echo "  Seeding demo database (130 decisions, 30 days of data)..."
  python seed_demo.py --clear 2>/dev/null | tail -4
else
  echo "  Database exists — skipping seed (use --seed to refresh)"
fi

# Kill any existing backend
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

echo -e "${YELLOW}[2/4] Starting backend (port 8000)...${NC}"
nohup uvicorn paaim.main:app --host 0.0.0.0 --port 8000 > /tmp/paaim-backend.log 2>&1 &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"

# Wait for backend to be ready
echo -n "  Waiting for API..."
for i in $(seq 1 20); do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e " ${GREEN}ready${NC}"
    break
  fi
  echo -n "."
  sleep 1
done

cd ..

# ── Frontend ──────────────────────────────────────────────────────────────────

echo -e "${YELLOW}[3/4] Setting up frontend...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
  echo "  Installing npm packages..."
  npm install --silent
fi

# Ensure .env.local is correct
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local

# Kill any existing frontend
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

echo -e "${YELLOW}[4/4] Starting frontend (port 3000)...${NC}"
nohup npm run dev > /tmp/paaim-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

echo -n "  Waiting for app..."
for i in $(seq 1 30); do
  if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e " ${GREEN}ready${NC}"
    break
  fi
  echo -n "."
  sleep 1
done

cd ..

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  PAAIM is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Dashboard:  http://localhost:3000"
echo "  API docs:   http://localhost:8000/docs"
echo ""
echo "  Login credentials:"
echo "    Email:    demo@paaim.io"
echo "    Password: demo123"
echo ""
echo "  Logs:"
echo "    Backend:  tail -f /tmp/paaim-backend.log"
echo "    Frontend: tail -f /tmp/paaim-frontend.log"
echo ""
echo "  Stop:  kill $BACKEND_PID $FRONTEND_PID"
echo ""

# Open browser (macOS)
if command -v open &>/dev/null; then
  sleep 2
  open http://localhost:3000
fi
