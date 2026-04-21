#!/usr/bin/env bash
# supervise_gemini_workers.sh — keep a target number of gemini_review_worker
# processes alive, respawning replacements for any that die.
#
# Usage:
#   scripts/supervise_gemini_workers.sh                 # default 20 workers
#   TARGET=100 scripts/supervise_gemini_workers.sh
#
# Stop:
#   touch /tmp/cob-gemini-stop
#   (or: pkill -f supervise_gemini_workers)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${TARGET:-20}"
STOP_FLAG="/tmp/cob-gemini-stop"
LOG_DIR="/tmp/cob-gemini-review"
KEY_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/cartha/gemini-vertex-sa.json}"
CHECK_INTERVAL_SECONDS=30
MAX_SPAWN_PER_CYCLE="${MAX_SPAWN_PER_CYCLE:-5}"
SPAWN_STAGGER_SECONDS="${SPAWN_STAGGER_SECONDS:-3}"
WORKER_SLEEP_SECONDS="${WORKER_SLEEP_SECONDS:-0.75}"
LOCATION_MODE="${LOCATION_MODE:-global}"

REGIONS=(us-central1 us-east1 us-west1 us-west4 europe-west4)

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

count_alive() {
  local matches
  matches="$(pgrep -f "tools/gemini_review_worker.py" || true)"
  if [[ -z "$matches" ]]; then
    echo 0
  else
    echo "$matches" | wc -l | tr -d ' '
  fi
}

next_worker_id() {
  find "$LOG_DIR" -maxdepth 1 -name 'worker-w*.log' -print 2>/dev/null \
    | sed 's/.*worker-w\([0-9]*\)\.log/\1/' \
    | sort -n | tail -1
}

spawn_worker() {
  local wid="$1"
  local location
  if [[ -n "${GCP_LOCATION:-}" ]]; then
    location="$GCP_LOCATION"
  elif [[ "$LOCATION_MODE" == "regional" ]]; then
    location="${REGIONS[$((RANDOM % ${#REGIONS[@]}))]}"
  else
    location="global"
  fi
  nohup env \
    GOOGLE_APPLICATION_CREDENTIALS="$KEY_PATH" \
    GCP_LOCATION="$location" \
    python3 "$REPO_ROOT/tools/gemini_review_worker.py" \
      --worker-id "w$wid" \
      --max-jobs 100000 \
      --sleep "$WORKER_SLEEP_SECONDS" \
    > "$LOG_DIR/worker-w$wid.log" 2>&1 &
  echo "  spawned w$wid @ $location"
}

echo "[$(date +%H:%M:%S)] supervise_gemini_workers starting; target=$TARGET"
echo "   stop with: touch $STOP_FLAG"
echo "   location_mode=$LOCATION_MODE stagger=${SPAWN_STAGGER_SECONDS}s max_spawn_per_cycle=$MAX_SPAWN_PER_CYCLE"

while true; do
  if [[ -f "$STOP_FLAG" ]]; then
    echo "[$(date +%H:%M:%S)] stop flag present; exiting (existing workers keep running)"
    rm -f "$STOP_FLAG"
    exit 0
  fi

  alive=$(count_alive)
  if (( alive < TARGET )); then
    missing=$((TARGET - alive))
    if (( missing > MAX_SPAWN_PER_CYCLE )); then
      missing=$MAX_SPAWN_PER_CYCLE
    fi
    max_existing=$(next_worker_id)
    max_existing=${max_existing:-0}
    echo "[$(date +%H:%M:%S)] alive=$alive target=$TARGET; spawning $missing"
    for ((i=1; i<=missing; i++)); do
      wid=$((max_existing + i))
      spawn_worker "$wid"
      sleep "$SPAWN_STAGGER_SECONDS"
    done
  fi

  # Quick check: if a region is failing, disable it? Out of scope; log-only.
  sleep "$CHECK_INTERVAL_SECONDS"
done
