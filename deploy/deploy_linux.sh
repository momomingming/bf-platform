#!/usr/bin/env bash
# LitAgent (bf-platform) one-time deployment on Aliyun ECS.
# Target OS: Ubuntu 22.04 LTS + Docker + Docker Compose v2.
# ASCII only on purpose: no non-ASCII bytes, so shell parsing can never break.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/litagent}"
REPO_URL="${REPO_URL:-https://github.com/momomingming/bf-platform.git}"
BRANCH="${BRANCH:-main}"
PORT="${PORT:-8501}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-300}"

log()  { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run this script as root"

log "step 1/6: environment"
. /etc/os-release
log "OS: $PRETTY_NAME  kernel: $(uname -r)"
df -h / | tail -1
free -m | head -2

log "step 2/6: install docker"
if command -v docker >/dev/null 2>&1; then
  log "docker present: $(docker --version)"
else
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi
docker compose version

log "step 3/6: fetch source into $APP_DIR"
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --all --tags
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
elif [ -z "$(ls -A "$APP_DIR")" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  die "$APP_DIR is not empty and is not a git repo; move it away and rerun"
fi
log "HEAD: $(git -C "$APP_DIR" rev-parse --short HEAD)"

log "step 4/6: build image"
mkdir -p "$APP_DIR/data"
cd "$APP_DIR"

# The host resolver is usually a systemd-resolved stub (127.0.0.53), which is
# useless inside containers. Give the daemon real resolvers.
install -d /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "dns": ["100.100.2.136", "100.100.2.138", "223.5.5.5", "119.29.29.29"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
systemctl restart docker

docker compose build

log "step 5/6: seed database (idempotent)"
# Runs tools/seed_db.py against the repo mounted at /repo, so the script resolves
# lis_battery_platform/ and lit_samples/ exactly as it does on a dev machine.
# --entrypoint python is required: the image ENTRYPOINT is "streamlit run app.py".
docker run --rm --entrypoint python \
  -v "$APP_DIR:/repo" \
  -w /repo \
  -e BF_DB_PATH=/repo/data/platform.db \
  bf-platform:latest tools/seed_db.py

log "step 6/6: start container"
docker compose up -d
docker compose ps

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

log "OK: health check passed"
log "local  : http://127.0.0.1:${PORT}"
log "public : http://$(curl -fsS --max-time 5 http://checkip.amazonaws.com 2>/dev/null || echo '<server-public-ip>'):${PORT}"
log "db file: $APP_DIR/data/platform.db"
