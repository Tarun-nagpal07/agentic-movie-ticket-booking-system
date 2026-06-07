#!/usr/bin/env bash
# ============================================================
# start.sh  —  One-click startup for Movie Ticket Booking App
# ============================================================
# Usage:
#   ./start.sh           # normal start
#   ./start.sh --force   # force re-seed data into Qdrant
# ============================================================

set -euo pipefail

# ── colours ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
header()  { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════${RESET}"; \
             echo -e "${BOLD}${CYAN}  $*${RESET}"; \
             echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}"; }

FORCE_SEED=""
if [[ "${1:-}" == "--force" ]]; then
  FORCE_SEED="--force"
  warn "Force flag detected — Qdrant data will be re-indexed."
fi

# ── resolve project root ─────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
info "Working directory: $SCRIPT_DIR"

# ── 0. check .env ────────────────────────────────────────────
header "Step 0 · Environment"
if [[ ! -f ".env" ]]; then
  error ".env file not found. Copy .env.example and fill in your keys."
  exit 1
fi
success ".env file found"

# ── 1. activate virtual environment ─────────────────────────
header "Step 1 · Virtual Environment"
VENV_PYTHON=""
if [[ -f ".venv/bin/python" ]]; then
  VENV_PYTHON=".venv/bin/python"
  VENV_PIP=".venv/bin/pip"
  VENV_UVICORN=".venv/bin/uvicorn"
  VENV_STREAMLIT=".venv/bin/streamlit"
  source .venv/bin/activate
  success "Activated .venv"
else
  warn ".venv not found — creating one with python3"
  python3 -m venv .venv
  source .venv/bin/activate
  VENV_PYTHON=".venv/bin/python"
  VENV_PIP=".venv/bin/pip"
  VENV_UVICORN=".venv/bin/uvicorn"
  VENV_STREAMLIT=".venv/bin/streamlit"
  info "Installing dependencies via pip (pyproject.toml / uv.lock)..."
  if command -v uv &>/dev/null; then
    uv pip install -e . --quiet
  else
    pip install -e . --quiet
  fi
  success "Dependencies installed"
fi

# ── 2. docker — redis, qdrant & postgres ────────────────────
header "Step 2 · Docker Services (Redis + Qdrant + Postgres)"

if ! command -v docker &>/dev/null; then
  error "Docker is not installed or not in PATH. Please install Docker Desktop."
  exit 1
fi

if ! docker info &>/dev/null 2>&1; then
  error "Docker daemon is not running. Please start Docker Desktop and try again."
  exit 1
fi

# Pull images if not already present (disabled to speed up start)
# info "Ensuring Redis image is available..."
# docker pull redis:7-alpine --quiet 2>&1 | tail -1 || true

# info "Ensuring Qdrant image is available..."
# docker pull qdrant/qdrant:latest --quiet 2>&1 | tail -1 || true

# ── Redis ────────────────────────────────────────────────────
REDIS_CONTAINER="movie-booking-redis"
if nc -z 127.0.0.1 6379 &>/dev/null || lsof -i tcp:6379 &>/dev/null; then
  success "Redis already running (port 6379 occupied)"
elif docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
  success "Redis container already running"
else
  if docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    info "Starting existing Redis container..."
    docker start "$REDIS_CONTAINER" > /dev/null
  else
    info "Creating and starting Redis container..."
    docker run -d \
      --name "$REDIS_CONTAINER" \
      -p 6379:6379 \
      --restart unless-stopped \
      -e REDIS_ARGS="--appendonly yes" \
      redis/redis-stack-server:latest > /dev/null
  fi
  success "Redis started on port 6379"
fi

# ── Qdrant ───────────────────────────────────────────────────
QDRANT_CONTAINER="movie-booking-qdrant"
if nc -z 127.0.0.1 6333 &>/dev/null || lsof -i tcp:6333 &>/dev/null; then
  success "Qdrant already running (port 6333 occupied)"
elif docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
  success "Qdrant container already running"
else
  if docker ps -a --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
    info "Starting existing Qdrant container..."
    docker start "$QDRANT_CONTAINER" > /dev/null
  else
    info "Creating and starting Qdrant container..."
    docker run -d \
      --name "$QDRANT_CONTAINER" \
      -p 6333:6333 \
      -p 6334:6334 \
      -v qdrant_movie_data:/qdrant/storage \
      --restart unless-stopped \
      qdrant/qdrant:latest > /dev/null
  fi
  success "Qdrant started on port 6333"
fi

# ── PostgreSQL ───────────────────────────────────────────────
POSTGRES_CONTAINER="movie-booking-postgres"
if nc -z 127.0.0.1 5432 &>/dev/null || lsof -i tcp:5432 &>/dev/null; then
  success "PostgreSQL already running (port 5432 occupied)"
elif docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
  success "PostgreSQL container already running"
else
  if docker ps -a --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    info "Starting existing PostgreSQL container..."
    docker start "$POSTGRES_CONTAINER" > /dev/null
  else
    info "Creating and starting PostgreSQL container..."
    docker run -d \
      --name "$POSTGRES_CONTAINER" \
      -p 5432:5432 \
      -e POSTGRES_PASSWORD=postgres \
      -e POSTGRES_USER=postgres \
      -e POSTGRES_DB=postgres \
      --restart unless-stopped \
      postgres:15-alpine > /dev/null
  fi
  success "PostgreSQL started on port 5432"
fi

# Determine active Redis and PostgreSQL container names for health check
ACTIVE_REDIS_CONTAINER=$(docker ps --filter "publish=6379" --format "{{.Names}}" | head -n 1)
if [[ -z "$ACTIVE_REDIS_CONTAINER" ]]; then
  ACTIVE_REDIS_CONTAINER="$REDIS_CONTAINER"
fi

ACTIVE_POSTGRES_CONTAINER=$(docker ps --filter "publish=5432" --format "{{.Names}}" | head -n 1)
if [[ -z "$ACTIVE_POSTGRES_CONTAINER" ]]; then
  ACTIVE_POSTGRES_CONTAINER="$POSTGRES_CONTAINER"
fi

# Wait for services to be ready
info "Waiting for services to be healthy..."
for i in {1..15}; do
  REDIS_OK=false
  QDRANT_OK=false
  POSTGRES_OK=false

  docker exec "$ACTIVE_REDIS_CONTAINER" redis-cli ping &>/dev/null && REDIS_OK=true
  curl -sf http://localhost:6333/healthz &>/dev/null && QDRANT_OK=true
  
  if nc -z 127.0.0.1 5432 &>/dev/null; then
    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
      docker exec "$ACTIVE_POSTGRES_CONTAINER" pg_isready -U postgres &>/dev/null && POSTGRES_OK=true
    else
      POSTGRES_OK=true
    fi
  fi

  if $REDIS_OK && $QDRANT_OK && $POSTGRES_OK; then
    break
  fi
  echo -n "."
  sleep 1
done
echo ""

if ! $REDIS_OK; then
  error "Redis did not become healthy in time."
  exit 1
fi
if ! $QDRANT_OK; then
  error "Qdrant did not become healthy in time."
  exit 1
fi
if ! $POSTGRES_OK; then
  error "PostgreSQL did not become healthy in time."
  exit 1
fi
success "Redis, Qdrant, and PostgreSQL are healthy ✓"

# ── 3. seed / ingest data ───────────────────────────────────
header "Step 3 · Data Ingestion (Policy Docs → Qdrant)"
info "Running ingestion.py${FORCE_SEED:+ with --force flag}..."
$VENV_PYTHON ingestion.py $FORCE_SEED
success "Data ingestion complete"

# ── 4. start FastAPI backend ─────────────────────────────────
header "Step 4 · FastAPI Backend"
BACKEND_PORT=8005
info "Starting FastAPI on http://127.0.0.1:$BACKEND_PORT ..."

# Kill any stale uvicorn on our port
if lsof -ti tcp:$BACKEND_PORT &>/dev/null; then
  warn "Port $BACKEND_PORT is busy — killing existing process..."
  kill $(lsof -ti tcp:$BACKEND_PORT) 2>/dev/null || true
  sleep 1
fi

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

$VENV_UVICORN main:app \
  --host 127.0.0.1 \
  --port $BACKEND_PORT \
  --log-level info \
  > "$LOG_DIR/backend.log" 2>&1 &

BACKEND_PID=$!
echo "$BACKEND_PID" > "$LOG_DIR/backend.pid"

# Wait for backend to be ready
info "Waiting for backend to start..."
for i in {1..20}; do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/" &>/dev/null; then
    break
  fi
  sleep 1
  echo -n "."
done
echo ""

if ! curl -sf "http://127.0.0.1:$BACKEND_PORT/" &>/dev/null; then
  error "Backend failed to start. Check $LOG_DIR/backend.log"
  cat "$LOG_DIR/backend.log" | tail -20
  exit 1
fi
success "FastAPI backend running  (PID $BACKEND_PID)  → http://127.0.0.1:$BACKEND_PORT"

# ── 5. start Streamlit frontend ──────────────────────────────
header "Step 5 · Streamlit Frontend"
STREAMLIT_PORT=8501

# Kill any stale streamlit on our port
if lsof -ti tcp:$STREAMLIT_PORT &>/dev/null; then
  warn "Port $STREAMLIT_PORT is busy — killing existing process..."
  kill $(lsof -ti tcp:$STREAMLIT_PORT) 2>/dev/null || true
  sleep 1
fi

info "Launching Streamlit on http://localhost:$STREAMLIT_PORT ..."

$VENV_STREAMLIT run app.py \
  --server.port $STREAMLIT_PORT \
  --server.address 127.0.0.1 \
  --server.headless false \
  > "$LOG_DIR/streamlit.log" 2>&1 &

STREAMLIT_PID=$!
echo "$STREAMLIT_PID" > "$LOG_DIR/streamlit.pid"

# Wait for streamlit to be ready
info "Waiting for Streamlit to start..."
for i in {1..20}; do
  if curl -sf "http://127.0.0.1:$STREAMLIT_PORT/" &>/dev/null; then
    break
  fi
  sleep 1
  echo -n "."
done
echo ""

success "Streamlit running  (PID $STREAMLIT_PID)  → http://localhost:$STREAMLIT_PORT"

# ── done ─────────────────────────────────────────────────────
header "🎬  All Systems Running!"
echo -e "
  ${BOLD}Services:${RESET}
    Redis       →  localhost:6379
    Qdrant      →  http://localhost:6333
    FastAPI     →  http://127.0.0.1:$BACKEND_PORT
    Streamlit   →  http://localhost:$STREAMLIT_PORT   ${GREEN}← open this in your browser${RESET}

  ${BOLD}Logs:${RESET}
    Backend     →  $LOG_DIR/backend.log
    Streamlit   →  $LOG_DIR/streamlit.log

  ${BOLD}To stop everything:${RESET}
    ./stop.sh
"

# Open browser automatically (macOS)
if command -v open &>/dev/null; then
  sleep 2
  open "http://localhost:$STREAMLIT_PORT"
fi

# Keep script alive so Ctrl+C cleanly shuts everything down
trap 'echo -e "\n${YELLOW}Shutting down...${RESET}"; kill $BACKEND_PID $STREAMLIT_PID 2>/dev/null; exit 0' INT TERM
info "Press Ctrl+C to stop both servers."
wait
