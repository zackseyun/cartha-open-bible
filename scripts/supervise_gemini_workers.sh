#!/usr/bin/env bash
# supervise_gemini_workers.sh — keep a target number of gemini_review_worker
# processes alive, respawning replacements for any that die.
#
# Usage:
#   scripts/supervise_gemini_workers.sh                 # default 75 workers
#   TARGET=100 scripts/supervise_gemini_workers.sh
#
# Stop:
#   touch /tmp/cob-gemini-stop
#   (or: pkill -f supervise_gemini_workers)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${TARGET:-75}"
STOP_FLAG="/tmp/cob-gemini-stop"
LOG_DIR="/tmp/cob-gemini-review"
KEY_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/cartha/gemini-vertex-sa.json}"
CHECK_INTERVAL_SECONDS=30

REGIONS=(us-central1 us-east1 us-west1 us-west4 europe-west4)

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

count_alive() {
  ps aux | grep '[g]emini_review_worker' | wc -l | tr -d ' '
}

next_worker_id() {
  ls "$LOG_DIR"/worker-w*.log 2>/dev/null \
    | sed 's/.*worker-w\([0-9]*\)\.log/\1/' \
    | sort -n | tail -1
}

spawn_worker() {
  local wid="$1"
  local region="${REGIONS[$((RANDOM % ${#REGIONS[@]}))]}"
  nohup env \
    GOOGLE_APPLICATION_CREDENTIALS="$KEY_PATH" \
    GCP_LOCATION="$region" \
    python3 "$REPO_ROOT/tools/gemini_review_worker.py" \
      --worker-id "w$wid" \
      --max-jobs 100000 \
      --sleep 0.5 \
    > "$LOG_DIR/worker-w$wid.log" 2>&1 &
  echo "  spawned w$wid @ $region"
}

echo "[$(date +%H:%M:%S)] supervise_gemini_workers starting; target=$TARGET"
echo "   stop with: touch $STOP_FLAG"

while true; do
  if [[ -f "$STOP_FLAG" ]]; then
    echo "[$(date +%H:%M:%S)] stop flag present; exiting (existing workers keep running)"
    rm -f "$STOP_FLAG"
    exit 0
  fi

  alive=$(count_alive)
  if (( alive < TARGET )); then
    missing=$((TARGET - alive))
    max_existing=$(next_worker_id)
    max_existing=${max_existing:-0}
    echo "[$(date +%H:%M:%S)] alive=$alive target=$TARGET; spawning $missing"
    for ((i=1; i<=missing; i++)); do
      wid=$((max_existing + i))
      spawn_worker "$wid"
    done
  fi

  # Quick check: if a region is failing, disable it? Out of scope; log-only.
  sleep "$CHECK_INTERVAL_SECONDS"
done
