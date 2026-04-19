#!/usr/bin/env bash
# supervise_worker.sh <worker_id> <phase> <worktree> [deployment_id]
#
# Run chapter_worker.py under a restart loop so a transient failure
# (DNS blip, Azure 500, read timeout) doesn't permanently kill a worker.
# The inner chapter_worker.py has 3-attempt draft retry with backoff
# inside; this wrapper handles crashes *above* that — network outages
# longer than the inner retry window, process kills, etc.
#
# Exit semantics:
#   inner exit 0 (queue drained with --stop-when-empty) -> stop, supervisor exits 0
#   inner exit !=0 (failure)                             -> restart after sleep
#   max 12 restarts before giving up (so a permanently-broken worker
#   doesn't spin forever)

set -u

WORKER_ID="${1:?worker_id required}"
PHASE="${2:?phase required}"
WORKTREE="${3:?worktree required}"
DEPLOYMENT_ID="${4:-}"
COORD="${COORD:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation}"
LOG="/tmp/cob-chapter-${WORKER_ID}.log"
MAX_RESTARTS="${MAX_RESTARTS:-12}"
RESTART_SLEEP_SECONDS="${RESTART_SLEEP_SECONDS:-15}"
PYTHON_BIN="${PYTHON_BIN:-$COORD/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -n "$DEPLOYMENT_ID" ]]; then
  export AZURE_OPENAI_DEPLOYMENT_ID="$DEPLOYMENT_ID"
fi

cd "$WORKTREE" || { echo "[supervisor] cannot cd to $WORKTREE" >>"$LOG"; exit 2; }

echo "[supervisor] started worker=$WORKER_ID phase=$PHASE wt=$WORKTREE deployment=${DEPLOYMENT_ID:-default} py=$PYTHON_BIN at $(date -u +%FT%TZ)" >> "$LOG"

restarts=0
while :; do
  "$PYTHON_BIN" tools/chapter_worker.py \
    --coord-root "$COORD" \
    --worker-id "$WORKER_ID" \
    --phase "$PHASE" \
    --backend azure-openai \
    --model gpt-5.4 \
    --max-jobs 30 \
    --stop-when-empty \
    >> "$LOG" 2>&1
  rc=$?

  if [[ "$rc" -eq 0 ]]; then
    echo "[supervisor] worker=$WORKER_ID exited 0 (queue drained); stopping" >> "$LOG"
    exit 0
  fi

  restarts=$((restarts + 1))
  echo "[supervisor] worker=$WORKER_ID exited $rc (restart $restarts/$MAX_RESTARTS); sleeping ${RESTART_SLEEP_SECONDS}s" >> "$LOG"

  if [[ "$restarts" -ge "$MAX_RESTARTS" ]]; then
    echo "[supervisor] worker=$WORKER_ID giving up after $MAX_RESTARTS restarts" >> "$LOG"
    exit 1
  fi

  sleep "$RESTART_SLEEP_SECONDS"
done
