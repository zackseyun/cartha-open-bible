#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 1 ]]; then
  echo "usage: supervise_merge.sh <phase...>" >&2
  exit 2
fi

PHASES=("$@")
COORD="${COORD:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation}"
PHASE_TAG="$(IFS=-; echo "${PHASES[*]}")"
LOG="/tmp/cob-merge-${PHASE_TAG}.log"
MAX_RESTARTS="${MAX_RESTARTS:-999999}"
RESTART_SLEEP_SECONDS="${RESTART_SLEEP_SECONDS:-20}"
PUBLISH_AFTER_PUSH="${PUBLISH_AFTER_PUSH:-1}"
PYTHON_BIN="${PYTHON_BIN:-$COORD/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

cd "$COORD" || exit 2
echo "[merge-supervisor] started phases=${PHASES[*]} py=$PYTHON_BIN at $(date -u +%FT%TZ)" >> "$LOG"

restarts=0
while :; do
  before_head="$(git rev-parse HEAD 2>/dev/null || true)"
  cmd=("$PYTHON_BIN" tools/chapter_merge.py --coord-root "$COORD" --limit 50 --push)
  for phase in "${PHASES[@]}"; do
    cmd+=(--phase "$phase")
  done
  "${cmd[@]}" >> "$LOG" 2>&1 || true
  after_head="$(git rev-parse HEAD 2>/dev/null || true)"

  if [[ -n "$before_head" && -n "$after_head" && "$before_head" != "$after_head" ]]; then
    echo "[merge-supervisor] phases=${PHASES[*]} merged new commits $before_head -> $after_head" >> "$LOG"
    if [[ "$PUBLISH_AFTER_PUSH" == "1" ]]; then
      "$COORD/scripts/publish_cob.sh" >> "$LOG" 2>&1 || true
    fi
  fi

  restarts=$((restarts + 1))
  if [[ "$restarts" -ge "$MAX_RESTARTS" ]]; then
    echo "[merge-supervisor] phases=${PHASES[*]} reached max restarts, exiting" >> "$LOG"
    exit 0
  fi
  sleep "$RESTART_SLEEP_SECONDS"
done
