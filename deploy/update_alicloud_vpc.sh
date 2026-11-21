#!/usr/bin/env bash
# Update LitAgent on an Aliyun ECS that has NO public IP.
#
# The instance cannot reach GitHub, so the source tree is refreshed from the
# outside (chunked payload transfer into $APP_DIR). This script then rebuilds
# the image, re-seeds the database and restarts the container.
#
# ASCII only on purpose.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/litagent}"
PORT="${PORT:-8501}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-300}"
PYPI_MIRROR="${PYPI_MIRROR:-http://mirrors.cloud.aliyuncs.com/pypi/simple/}"
PIP_TRUSTED="${PIP_TRUSTED_HOST:-mirrors.cloud.aliyuncs.com}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
[ -d "$APP_DIR" ] || die "$APP_DIR not found"

cd "$APP_DIR"

log "step 1/5: back up the current database"
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"
if [ -f data/platform.db ]; then
  cp data/platform.db "backups/platform.db.$stamp"
  log "backed up to backups/platform.db.$stamp"
fi

log "step 2/5: rebuild the image"
export PIP_INDEX_URL="$PYPI_MIRROR"
export PIP_TRUSTED_HOST="$PIP_TRUSTED"
export BASE_IMAGE="${BASE_IMAGE:-python:3.11-slim}"
docker compose build

log "step 3/5: re-seed the database (idempotent)"
docker run --rm --entrypoint python \
  -v "$APP_DIR:/repo" \
  -w /repo \
  -e BF_DB_PATH=/repo/data/platform.db \
  bf-platform:latest tools/seed_db.py

log "step 4/5: restart the container"
docker compose up -d
docker image prune -f

log "step 5/5: wait for the health endpoint (timeout ${HEALTH_TIMEOUT}s)"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
until curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    docker compose logs --tail 80 bf-platform
    die "container did not become healthy"
  fi
  sleep 3
done

log "OK: healthy on port ${PORT}"
log "internal URL: http://$(hostname -I | awk '{print $1}'):${PORT}"
