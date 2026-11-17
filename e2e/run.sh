#!/usr/bin/env bash
# Startet eine frische Open-WebUI-Instanz, spielt das Repo ein und testet.
# Aufruf aus dem Repo-Wurzelordner: e2e/run.sh
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f e2e/docker-compose.yml up -d --wait
trap 'docker compose -f e2e/docker-compose.yml down -v' EXIT

OWUI_URL="${OWUI_URL:-http://localhost:3000}" uv run pytest e2e -v
