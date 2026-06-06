#!/usr/bin/env bash
# ============================================================
# stop.sh  —  Stop all Movie Ticket Booking services
# ============================================================
# Usage:
#   ./stop.sh            # stop backend + streamlit (keep docker)
#   ./stop.sh --all      # also stop Redis and Qdrant containers
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

STOP_DOCKER=false
[[ "${1:-}" == "--all" ]] && STOP_DOCKER=true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
LOG_DIR="logs"

# ── kill backend ─────────────────────────────────────────────
if [[ -f "$LOG_DIR/backend.pid" ]]; then
  PID=$(cat "$LOG_DIR/backend.pid")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && success "FastAPI backend stopped (PID $PID)"
  else
    warn "Backend PID $PID not running"
  fi
  rm -f "$LOG_DIR/backend.pid"
else
  # Fallback: kill by port
  if lsof -ti tcp:8005 &>/dev/null; then
    kill $(lsof -ti tcp:8005) && success "FastAPI stopped (killed by port)"
  else
    info "No backend process found on port 8005"
  fi
fi

# ── kill streamlit ───────────────────────────────────────────
if [[ -f "$LOG_DIR/streamlit.pid" ]]; then
  PID=$(cat "$LOG_DIR/streamlit.pid")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && success "Streamlit stopped (PID $PID)"
  else
    warn "Streamlit PID $PID not running"
  fi
  rm -f "$LOG_DIR/streamlit.pid"
else
  if lsof -ti tcp:8501 &>/dev/null; then
    kill $(lsof -ti tcp:8501) && success "Streamlit stopped (killed by port)"
  else
    info "No Streamlit process found on port 8501"
  fi
fi

# ── optionally stop docker containers ───────────────────────
if $STOP_DOCKER; then
  info "Stopping Docker containers..."
  docker stop movie-booking-redis movie-booking-qdrant movie-booking-postgres 2>/dev/null && success "Docker containers stopped" || warn "Some containers were already stopped"
else
  info "Docker containers (Redis, Qdrant, PostgreSQL) left running. Use './stop.sh --all' to also stop them."
fi

echo -e "\n${BOLD}${GREEN}All done. Goodbye! 🎬${RESET}\n"
