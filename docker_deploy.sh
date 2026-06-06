#!/usr/bin/env bash
# ============================================================
# docker_deploy.sh  —  Build, Push, Pull, and Run Movie Ticket Booking
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
error()   { echo -e "${RED}[ERROR]${RESET} $*"; }

IMAGE_NAME="movie-booking-app"
VERSION="latest"

show_help() {
  echo -e "
${BOLD}Usage:${RESET}
  $0 <command> [arguments]

${BOLD}Commands:${RESET}
  ${BOLD}build${RESET}              Build the unified Docker image locally (${IMAGE_NAME}:${VERSION})
  ${BOLD}push <repo>${RESET}         Tag the local image and push to your container registry (e.g. docker.io/username/movie-booking-app)
  ${BOLD}pull <repo>${RESET}         Pull an image from a registry and tag it locally as ${IMAGE_NAME}:${VERSION}
  ${BOLD}run${RESET}               Spin up all services (Backend, Frontend, Redis, Qdrant, Postgres) using Docker Compose
  ${BOLD}stop${RESET}              Stop and remove all running services using Docker Compose
  ${BOLD}logs${RESET}              Follow log output from the running Docker Compose containers

${BOLD}Examples:${RESET}
  $0 build
  $0 push docker.io/myusername/movie-booking-app
  $0 pull docker.io/myusername/movie-booking-app
  $0 run
"
}

if [[ $# -lt 1 ]]; then
  show_help
  exit 1
fi

COMMAND="$1"

case "$COMMAND" in
  build)
    info "Building unified Docker image '${IMAGE_NAME}:${VERSION}'..."
    docker build -t "${IMAGE_NAME}:${VERSION}" .
    success "Docker image '${IMAGE_NAME}:${VERSION}' built successfully!"
    ;;

  push)
    if [[ $# -lt 2 ]]; then
      error "Missing registry/repository name. Usage: $0 push <registry_username/repository>"
      exit 1
    fi
    REPO="$2"
    info "Tagging local image '${IMAGE_NAME}:${VERSION}' as '${REPO}:${VERSION}'..."
    docker tag "${IMAGE_NAME}:${VERSION}" "${REPO}:${VERSION}"
    
    info "Pushing '${REPO}:${VERSION}' to container registry..."
    docker push "${REPO}:${VERSION}"
    success "Image '${REPO}:${VERSION}' uploaded successfully!"
    ;;

  pull)
    if [[ $# -lt 2 ]]; then
      error "Missing registry/repository name. Usage: $0 pull <registry_username/repository>"
      exit 1
    fi
    REPO="$2"
    info "Pulling '${REPO}:${VERSION}' from container registry..."
    docker pull "${REPO}:${VERSION}"
    
    info "Re-tagging pulled image as '${IMAGE_NAME}:${VERSION}' for local use..."
    docker tag "${REPO}:${VERSION}" "${IMAGE_NAME}:${VERSION}"
    success "Image pulled and configured as '${IMAGE_NAME}:${VERSION}'!"
    ;;

  run)
    info "Verifying that .env file exists..."
    if [[ ! -f ".env" ]]; then
      warn ".env file not found. Copying .env.example to .env..."
      cp .env.example .env
      warn "Please fill in your environment API keys in .env!"
    fi
    
    info "Starting all services via Docker Compose..."
    docker compose up -d
    success "All services are starting up! Check access at:"
    echo -e "    FastAPI Backend   → http://localhost:8005/"
    echo -e "    Streamlit Frontend → http://localhost:8501/"
    ;;

  stop)
    info "Stopping all container services..."
    docker compose down
    success "All container services stopped successfully."
    ;;

  logs)
    info "Tailing container logs..."
    docker compose logs -f
    ;;

  *)
    error "Unknown command: $COMMAND"
    show_help
    exit 1
    ;;
esac
