#!/usr/bin/env bash
# LitAgent deploy on an Aliyun ECS that has NO public IP and NO NAT gateway.
# Everything (apt, docker CE, pypi, docker hub) is pulled from Aliyun VPC-internal mirrors.
# The source code is expected to be already extracted at $APP_DIR.
# ASCII only on purpose.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/litagent}"
PORT="${PORT:-8501}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-300}"

APT_MIRROR="${APT_MIRROR:-mirrors.cloud.aliyuncs.com}"
DOCKER_MIRROR="${DOCKER_MIRROR:-registry-vpc.cn-beijing.aliyuncs.com}"
PYPI_MIRROR="${PYPI_MIRROR:-http://mirrors.cloud.aliyuncs.com/pypi/simple/}"
PIP_TRUSTED="${PIP_TRUSTED_HOST:-mirrors.cloud.aliyuncs.com}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
[ -d "$APP_DIR" ] || die "$APP_DIR not found; transfer the source tree first"

log "step 1/7: install docker from $APT_MIRROR"
if ! command -v docker >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "http://${APT_MIRROR}/docker-ce/linux/ubuntu/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] http://${APT_MIRROR}/docker-ce/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "docker present: $(docker --version)"
fi
docker compose version

log "step 2/7: point docker at the VPC registry mirror and a working resolver"
install -d /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["https://${DOCKER_MIRROR}"],
  "dns": ["${DNS_SERVER:-100.100.2.136}", "100.100.2.138"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
systemctl restart docker
systemctl is-active --quiet docker || die "docker failed to restart"

log "step 3/7: point pip at the VPC pypi mirror"
cat > /etc/pip.conf <<EOF
[global]
index-url = ${PYPI_MIRROR}
trusted-host = ${PIP_TRUSTED}
timeout = 60
EOF
cat /etc/pip.conf

log "step 4/7: fetch the base image"
BASE_IMAGE="${BASE_IMAGE:-python:3.11-slim}"
if docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
  log "base image already present locally"
elif docker pull "$BASE_IMAGE"; then
  log "pulled $BASE_IMAGE"
else
  log "pull failed, building an equivalent base image from the internal apt mirror"
  bash "$APP_DIR/deploy/build_base_image.sh"
  BASE_IMAGE="python:3.11-slim"
fi
docker tag "$BASE_IMAGE" python:3.11-slim

log "step 5/7: build the app image"
cd "$APP_DIR"
export PIP_INDEX_URL="$PYPI_MIRROR"
export PIP_TRUSTED_HOST="$PIP_TRUSTED"
export BASE_IMAGE="$BASE_IMAGE"
mkdir -p data
docker compose build

log "step 6/7: seed the database (idempotent)"
# The repo is mounted at /repo so tools/seed_db.py resolves
# lis_battery_platform/ and lit_samples/ exactly as on a dev machine.
docker run --rm --entrypoint python \
  -v "$APP_DIR:/repo" \
  -w /repo \
  -e BF_DB_PATH=/repo/data/platform.db \
  bf-platform:latest tools/seed_db.py

log "step 7/7: start the container"
docker compose up -d
docker compose ps

log "waiting for health endpoint (timeout ${HEALTH_TIMEOUT}s)"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
until curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    log "health check failed, recent logs:"
    docker compose logs --tail 80 bf-platform
    die "container did not become healthy"
  fi
  sleep 3
done

log "OK: healthy on port ${PORT}"
log "db file: $APP_DIR/data/platform.db"
log "internal URL: http://$(hostname -I | awk '{print $1}'):${PORT}"
