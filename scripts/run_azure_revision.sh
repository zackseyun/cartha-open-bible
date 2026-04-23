#!/usr/bin/env bash
# run_azure_revision.sh — launch the Azure GPT-5.4 bulk revision pass
# in the background with logging.
#
# Usage:
#   scripts/run_azure_revision.sh                     # all testaments, 20 workers
#   CONCURRENCY=30 scripts/run_azure_revision.sh
#   TESTAMENT="nt" scripts/run_azure_revision.sh      # nt only
#   DRY_RUN=1 scripts/run_azure_revision.sh           # count only
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/tmp/azure-revision.log"
CONCURRENCY="${CONCURRENCY:-20}"
TESTAMENT="${TESTAMENT:-nt ot extra_canonical deuterocanon}"
DRY_RUN="${DRY_RUN:-0}"

if [[ "$DRY_RUN" == "1" ]]; then
  python3 "$REPO_ROOT/tools/azure_bulk_revise.py" \
    --testament $TESTAMENT \
    --dry-run
  exit 0
fi

echo "[$(date)] Starting Azure revision pass — log: $LOG"
echo "  concurrency=$CONCURRENCY testament=$TESTAMENT"

nohup python3 "$REPO_ROOT/tools/azure_bulk_revise.py" \
  --testament $TESTAMENT \
  --concurrency "$CONCURRENCY" \
  > "$LOG" 2>&1 &

PID=$!
echo "  PID=$PID"
echo "  Monitor: tail -f $LOG"
echo "  Stop:    kill $PID"
