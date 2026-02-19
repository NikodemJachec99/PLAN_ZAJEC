#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_URL="${APP_URL:-https://patryk225-30225.wykr.es}"
COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "ERROR: docker compose is not available."
  exit 1
fi

echo "[1/4] git pull --ff-only"
git pull --ff-only

echo "[2/4] docker compose build"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" build --pull

echo "[3/4] docker compose up -d"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up -d --remove-orphans

echo "[4/4] docker image prune -f"
docker image prune -f >/dev/null || true

echo
echo "Deploy completed."
echo "Public URL: ${APP_URL}"
echo "Alt URL: https://patryk225-30225.mikrus.cloud"
echo
echo "Useful commands:"
echo "  ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} ps"
echo "  ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} logs -f"

