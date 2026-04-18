#!/usr/bin/env bash
# deploy.sh — rsync the repo to a Dedalus VM and install the matching systemd
# unit. Idempotent: rerun after each code change. Expected to be invoked from
# the repo root.
#
# Usage: infra/scripts/deploy.sh <vm-host> <agent>
#   <vm-host>  ssh target, e.g. scout-vm
#   <agent>    one of: scout | analyst | strategist
#
# Env:
#   REMOTE_USER  ssh user on the VM (default: root)
#   REMOTE_DIR   target install dir (default: /opt/supplai)

set -euo pipefail

usage() {
  cat <<'EOF'
deploy.sh — deploy a suppl.ai agent to a Dedalus VM.

Usage:
  infra/scripts/deploy.sh <vm-host> <agent>

  <vm-host>  ssh target (e.g. scout-vm.dedalus.io)
  <agent>    one of: scout | analyst | strategist

Env:
  REMOTE_USER  ssh user (default: root)
  REMOTE_DIR   install dir (default: /opt/supplai)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

VM_HOST="$1"
AGENT="$2"

case "$AGENT" in
  scout|analyst|strategist) ;;
  *) echo "error: agent must be scout | analyst | strategist (got: $AGENT)" >&2; exit 2 ;;
esac

REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/opt/supplai}"
SSH_TARGET="${REMOTE_USER}@${VM_HOST}"
UNIT_SRC="infra/systemd/supplai-${AGENT}.service"
UNIT_NAME="supplai-${AGENT}.service"

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "error: $UNIT_SRC not found — run from repo root" >&2
  exit 1
fi

echo "==> deploying $AGENT to $SSH_TARGET:$REMOTE_DIR"

# 1. rsync code (excluding vcs, venvs, caches, frontend)
rsync -az --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='web/node_modules/' \
  --exclude='web/.next/' \
  ./ "$SSH_TARGET:$REMOTE_DIR/"

# 2. install systemd unit
scp "$UNIT_SRC" "$SSH_TARGET:/etc/systemd/system/$UNIT_NAME"

# 3. reload + enable + restart
ssh "$SSH_TARGET" bash -s <<EOF
set -euo pipefail
systemctl daemon-reload
systemctl enable "$UNIT_NAME"
systemctl restart "$UNIT_NAME"
systemctl --no-pager --lines=0 status "$UNIT_NAME" || true
EOF

echo "==> $AGENT deployed. Tail logs: ssh $SSH_TARGET journalctl -u $UNIT_NAME -f"
