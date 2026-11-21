#!/usr/bin/env bash
# LitAgent one-command update: pull latest main, rebuild, restart, health check.
# Data in ./data (SQLite db + model artifacts) is never touched by this script.
# ASCII only on purpose.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/litagent}"
BRANCH="${BRANCH:-main}"
PORT="${PORT:-8501}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-300}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run this script as root"
[ -d "$APP_DIR/.git" ] || die "$APP_DIR is not a git repo"

cd "$APP_DIR"

log "backup database"
mkdir -p backups
if [ -f data/platform.db ]; then
  cp data/platform.db "backups/platform.db.$(date +%Y%m%d-%H%M%S)"
  log "saved backups/platform.db.$(date +%Y%m%d-%H%M%S)"
else
  log "no data/platform.db yet, skip backup"
fi

log "pull $BRANCH"
git fetch --all --tags
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
log "HEAD: $(git rev-parse --short HEAD)"

log "rebuild and restart"
docker compose up -d --build
docker image prune -f

log "waiting for health endpoint (timeout ${HEALTH_TIMEOUT}s)"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
until curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    log "health check failed, recent logs:"
    docker compose logs --tail 50 bf-platform
    die "container did not become healthy"
  fi
  sleep 3
done

docker compose ps
log "OK: updated and healthy on port ${PORT}"
