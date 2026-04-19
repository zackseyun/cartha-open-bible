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

# Fetch the CDN's currently-published commit sha. Used to decide whether
# a republish is needed even when the current cycle didn't advance HEAD
# (e.g. another session pushed directly, status.json regen, or a manual
# commit that bypassed this supervisor).
cdn_published_sha() {
  curl -sL --max-time 10 "https://bible.cartha.com/manifest.json" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('commit_sha',''))" 2>/dev/null \
    || true
}

restarts=0
while :; do
  before_head="$(git rev-parse HEAD 2>/dev/null || true)"
  cmd=("$PYTHON_BIN" tools/chapter_merge.py --coord-root "$COORD" --limit 50 --push)
  for phase in "${PHASES[@]}"; do
    cmd+=(--phase "$phase")
  done
  "${cmd[@]}" >> "$LOG" 2>&1 || true
  after_head="$(git rev-parse HEAD 2>/dev/null || true)"

  if [[ "$PUBLISH_AFTER_PUSH" == "1" ]]; then
    should_publish=0
    reason=""
    if [[ -n "$before_head" && -n "$after_head" && "$before_head" != "$after_head" ]]; then
      should_publish=1
      reason="local_advanced $before_head->$after_head"
    else
      # Even if this cycle didn't advance HEAD, the CDN may still be behind
      # main — e.g. another merge lane or a manual commit pushed since we
      # last published. Check the CDN's manifest and republish if its
      # commit_sha differs from ours.
      cdn_sha="$(cdn_published_sha)"
      if [[ -n "$cdn_sha" && -n "$after_head" && "$cdn_sha" != "$after_head" ]]; then
        should_publish=1
        reason="cdn_stale cdn=${cdn_sha:0:12} main=${after_head:0:12}"
      fi
    fi
    if [[ "$should_publish" == "1" ]]; then
      echo "[merge-supervisor] phases=${PHASES[*]} publishing — $reason" >> "$LOG"
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
