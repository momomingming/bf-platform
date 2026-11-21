#!/usr/bin/env bash
# Build a minimal Ubuntu 22.04 + Python 3.11 Docker base image using ONLY the
# VPC-internal apt mirror.
#
# Needed when the instance cannot reach Docker Hub (no EIP, no NAT gateway):
# the standard python:3.11-slim image cannot be pulled, so we assemble an
# equivalent base image locally and import it.
#
# Result: an image tagged python:3.11-slim AND litagent-base:py311
# ASCII only on purpose.
set -euo pipefail

MIRROR="${APT_MIRROR:-http://mirrors.cloud.aliyuncs.com/ubuntu}"
SUITE="${SUITE:-jammy}"
ROOTFS="${ROOTFS:-/root/litagent-rootfs}"
TAG="${BASE_IMAGE_TAG:-litagent-base:py311}"
DNS="${DNS_SERVER:-100.100.2.136}"
PYPI_MIRROR="${PYPI_MIRROR:-http://mirrors.cloud.aliyuncs.com/pypi/simple/}"
PIP_TRUSTED="${PIP_TRUSTED_HOST:-mirrors.cloud.aliyuncs.com}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
command -v docker >/dev/null 2>&1 || die "docker is not installed"

log "step 1/5: install debootstrap"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq debootstrap

log "step 2/5: debootstrap $SUITE"
if [ -d "$ROOTFS" ] && [ -f "$ROOTFS/etc/debian_version" ]; then
  log "rootfs already exists, reuse it"
else
  rm -rf "$ROOTFS"
  debootstrap --variant=minbase \
    --components=main,universe,restricted,multiverse \
    --include=ca-certificates \
    "$SUITE" "$ROOTFS" "$MIRROR" >/dev/null 2>&1 || die "debootstrap failed"
fi

log "step 3/5: install python3.11 and build tools inside the rootfs"
# The host resolver is a systemd-resolved stub (127.0.0.53) and is useless
# inside a chroot, so write a real Aliyun VPC resolver instead.
printf 'nameserver %s\n' "$DNS" > "$ROOTFS/etc/resolv.conf"

# debootstrap only writes the base suite; python3.11 lives in universe of
# jammy-updates, so the pocket has to be added explicitly.
cat > "$ROOTFS/etc/apt/sources.list" <<EOF
deb $MIRROR $SUITE main restricted universe multiverse
deb $MIRROR $SUITE-updates main restricted universe multiverse
deb $MIRROR $SUITE-security main restricted universe multiverse
EOF

# Stale bind mounts from an interrupted run would be stacked again here and
# would end up inside the imported image, so drop them first.
umount -R -l "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev" 2>/dev/null || true
mount --bind /proc "$ROOTFS/proc"
mount --bind /sys "$ROOTFS/sys"
mount --bind /dev "$ROOTFS/dev"
cleanup() {
  umount -R -l "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev" 2>/dev/null || true
}
trap cleanup EXIT

chroot "$ROOTFS" apt-get update -qq
chroot "$ROOTFS" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
  python3.11 python3.11-venv ca-certificates curl gcc
chroot "$ROOTFS" apt-get clean
chroot "$ROOTFS" rm -rf /var/lib/apt/lists/*

log "step 4/5: create a python3.11 venv with pip on PATH"
# The VPC has no outbound route to pypi.org, so pip inside the rootfs must
# use the Aliyun internal mirror as well.
cat > "$ROOTFS/etc/pip.conf" <<EOF
[global]
index-url = ${PYPI_MIRROR}
trusted-host = ${PIP_TRUSTED}
timeout = 60
EOF
chroot "$ROOTFS" python3.11 -m venv /opt/venv
chroot "$ROOTFS" env PIP_INDEX_URL="${PYPI_MIRROR}" PIP_TRUSTED_HOST="${PIP_TRUSTED}" \
  /opt/venv/bin/pip install -q --upgrade pip || log "pip upgrade skipped (mirror or network)"
chroot "$ROOTFS" ln -sf /opt/venv/bin/pip /usr/local/bin/pip
chroot "$ROOTFS" ln -sf /opt/venv/bin/pip3 /usr/local/bin/pip3
# A symlinked python resolves to the system interpreter and loses the venv
# site-packages, so use a wrapper that execs the venv interpreter directly.
mkdir -p "$ROOTFS/usr/local/bin" || log "cannot create $ROOTFS/usr/local/bin, relying on PATH"
for exe in python python3; do
  printf '#!/bin/sh\nexec /opt/venv/bin/%s "$@"\n' "$exe" > "$ROOTFS/usr/local/bin/$exe" \
    && chmod +x "$ROOTFS/usr/local/bin/$exe" \
    || log "wrapper for $exe skipped"
done

log "step 5/5: import into docker"
cleanup
trap - EXIT
tar -C "$ROOTFS" -c . | docker import - "$TAG"
docker tag "$TAG" python:3.11-slim
docker images | head -5
log "done: $TAG (also tagged python:3.11-slim)"
