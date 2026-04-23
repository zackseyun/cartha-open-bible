#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${TARGET:-24}"
LOG_DIR="${LOG_DIR:-/tmp/cob-testaments-draft}"
STOP_FILE="${STOP_FILE:-/tmp/cob-testaments-stop}"
SPAWN_STAGGER_SECONDS="${SPAWN_STAGGER_SECONDS:-2}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

"$PYTHON_BIN" tools/testaments_draft_queue.py init >/dev/null

deployments=(
  "gpt-5-4-deployment"
  "gpt-5-4-translation-b"
  "gpt-5-4-translation-c"
)

echo "[$(date +%H:%M:%S)] launching Testament draft workers target=$TARGET"
echo " stop with: touch $STOP_FILE"

for i in $(seq 1 "$TARGET"); do
  dep_index=$(( (i - 1) % ${#deployments[@]} ))
  deployment="${deployments[$dep_index]}"
  worker_id="$(printf 't12p-w%02d' "$i")"
  nohup env \
    PYTHONUNBUFFERED=1 \
    "$PYTHON_BIN" "$REPO_ROOT/tools/testaments_draft_worker.py" \
      --worker-id "$worker_id" \
      --deployment "$deployment" \
    > "$LOG_DIR/$worker_id.log" 2>&1 &
  echo "[$(date +%H:%M:%S)] spawned $worker_id deployment=$deployment"
  sleep "$SPAWN_STAGGER_SECONDS"
done

echo "[$(date +%H:%M:%S)] workers launched; logs in $LOG_DIR"
