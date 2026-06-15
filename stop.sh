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

# Helper to read .env values safely
get_env_val() {
  local key=$1
  local env_val
  eval env_val=\${$key:-}
  if [[ -n "$env_val" ]]; then
    echo "$env_val"
  elif [[ -f ".env" && -n "$(grep "^${key}[[:space:]]*=" .env || echo '')" ]]; then
    grep "^${key}[[:space:]]*=" .env | tail -n 1 | cut -d'=' -f2- | tr -d '"'\''\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
  else
    echo ""
  fi
}

# Check if a URL is local
is_local() {
  local url=$1
  if [[ -z "$url" ]]; then
    echo "false"
  elif [[ "$url" =~ "localhost" || "$url" =~ "127.0.0.1" ]]; then
    echo "true"
  else
    echo "false"
  fi
}

REDIS_URL=$(get_env_val "REDIS_URL")
QDRANT_URL=$(get_env_val "QDRANT_URL")
SUPABASE_DB_URL=$(get_env_val "SUPABASE_DB_URL")

REDIS_LOCAL=$(is_local "$REDIS_URL")
QDRANT_LOCAL=$(is_local "$QDRANT_URL")
POSTGRES_LOCAL=$(is_local "$SUPABASE_DB_URL")

NEED_DOCKER=false
if [[ "$REDIS_LOCAL" == "true" || "$QDRANT_LOCAL" == "true" || "$POSTGRES_LOCAL" == "true" ]]; then
  NEED_DOCKER=true
fi

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
if $NEED_DOCKER; then
  if $STOP_DOCKER; then
    info "Stopping Docker containers..."
    docker stop movie-booking-redis movie-booking-qdrant movie-booking-postgres 2>/dev/null && success "Docker containers stopped" || warn "Some containers were already stopped"
  else
    info "Docker containers (Redis, Qdrant, PostgreSQL) left running. Use './stop.sh --all' to also stop them."
  fi
else
  info "All database services are cloud-based. Skipping Docker checks."
fi

echo -e "\n${BOLD}${GREEN}All done. Goodbye! 🎬${RESET}\n"
