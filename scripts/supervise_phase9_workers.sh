#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${TARGET:-24}"
STOP_FLAG="/tmp/cob-phase9-stop"
LOG_DIR="/tmp/cob-phase9-workers"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-20}"
SPAWN_STAGGER_SECONDS="${SPAWN_STAGGER_SECONDS:-2}"
PHASE="phase8"
MODEL="${MODEL:-gpt-5.4}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi
mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"
fetch_azure_key() {
  if [[ -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
    AZURE_OPENAI_API_KEY="$(aws secretsmanager get-secret-value \
      --secret-id cartha-azure-openai-key --region us-west-2 \
      --query SecretString --output text \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['api_key'])")"
    export AZURE_OPENAI_API_KEY
    export AZURE_OPENAI_ENDPOINT="https://eastus2.api.cognitive.microsoft.com"
    export AZURE_OPENAI_DEPLOYMENT_ID="gpt-5-4-deployment"
    export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
  fi
}
declare -a SLOTS=(
  "phase9-wis-w1 /private/tmp/cartha-translation-phase9-wis-w1 gpt-5-4-deployment"
  "phase9-wis-w2 /private/tmp/cartha-translation-phase9-wis-w2 gpt-5-4-translation-b"
  "phase9-wis-w3 /private/tmp/cartha-translation-phase9-wis-w3 gpt-5-4-translation-c"
  "phase9-wis-w9 /private/tmp/cartha-translation-phase9-wis-w9 gpt-5-4-deployment"
  "phase9-wis-w10 /private/tmp/cartha-translation-phase9-wis-w10 gpt-5-4-translation-b"
  "phase9-wis-w11 /private/tmp/cartha-translation-phase9-wis-w11 gpt-5-4-translation-c"
  "phase9-deut-w4 /private/tmp/cartha-translation-phase9-deut-w4 gpt-5-4-deployment"
  "phase9-deut-w5 /private/tmp/cartha-translation-phase9-deut-w5 gpt-5-4-translation-b"
  "phase9-deut-w6 /private/tmp/cartha-translation-phase9-deut-w6 gpt-5-4-translation-c"
  "phase9-wis-w4 /private/tmp/cartha-translation-phase9-wis-w4 gpt-5-4-deployment"
  "phase9-wis-w5 /private/tmp/cartha-translation-phase9-wis-w5 gpt-5-4-translation-b"
  "phase9-wis-w6 /private/tmp/cartha-translation-phase9-wis-w6 gpt-5-4-translation-c"
  "phase9-wis-w7 /private/tmp/cartha-translation-phase9-wis-w7 gpt-5-4-deployment"
  "phase9-wis-w8 /private/tmp/cartha-translation-phase9-wis-w8 gpt-5-4-translation-b"
  "phase9-wis-w12 /private/tmp/cartha-translation-phase9-wis-w12 gpt-5-4-translation-c"
  "phase9-wis-w13 /private/tmp/cartha-translation-phase9-wis-w13 gpt-5-4-deployment"
  "phase9-wis-w14 /private/tmp/cartha-translation-phase9-wis-w14 gpt-5-4-translation-b"
  "phase9-wis-w15 /private/tmp/cartha-translation-phase9-wis-w15 gpt-5-4-translation-c"
  "phase9-wis-w16 /private/tmp/cartha-translation-phase9-wis-w16 gpt-5-4-deployment"
  "phase9-wis-w17 /private/tmp/cartha-translation-phase9-wis-w17 gpt-5-4-translation-b"
  "phase9-wis-w18 /private/tmp/cartha-translation-phase9-wis-w18 gpt-5-4-translation-c"
  "phase9-deut-w13 /private/tmp/cartha-translation-phase9-deut-w13 gpt-5-4-deployment"
  "phase9-deut-w14 /private/tmp/cartha-translation-phase9-deut-w14 gpt-5-4-translation-b"
  "phase9-deut-w15 /private/tmp/cartha-translation-phase9-deut-w15 gpt-5-4-translation-c"
)
is_alive() {
  local wid="$1"
  local matches
  matches="$(pgrep -af "scripts/supervise_worker.sh ${wid} ${PHASE} " || true)"
  [[ -n "${matches//[[:space:]]/}" ]]
}
count_alive() {
  local matches
  matches="$(pgrep -af "scripts/supervise_worker.sh .* ${PHASE} " || true)"
  if [[ -z "${matches//[[:space:]]/}" ]]; then
    echo 0
  else
    printf '%s\n' "$matches" | wc -l | tr -d ' '
  fi
}
spawn_slot() {
  local wid="$1"
  local wt="$2"
  local deployment="$3"
  [[ -d "$wt" ]] || return 0
  fetch_azure_key
  nohup env \
    AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_DEPLOYMENT_ID="$AZURE_OPENAI_DEPLOYMENT_ID" \
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
    COORD="$REPO_ROOT" \
    PYTHON_BIN="$PYTHON_BIN" \
    "$REPO_ROOT/scripts/supervise_worker.sh" \
      "$wid" \
      "$PHASE" \
      "$wt" \
      "$deployment" \
    > "$LOG_DIR/$wid.log" 2>&1 &
  echo "[$(date +%H:%M:%S)] spawned $wid -> $wt (deployment=$deployment)"
}
echo "[$(date +%H:%M:%S)] supervise_phase9_workers starting; target=$TARGET phase=$PHASE"
echo " stop with: touch $STOP_FLAG"
while true; do
  if [[ -f "$STOP_FLAG" ]]; then
    echo "[$(date +%H:%M:%S)] stop flag present; exiting (existing workers keep running)"
    rm -f "$STOP_FLAG"
    exit 0
  fi
  "$PYTHON_BIN" "$REPO_ROOT/tools/chapter_queue.py" init --phase "$PHASE" --reset-failed >/dev/null
  alive="$(count_alive)"
  if (( alive < TARGET )); then
    need=$((TARGET - alive))
    echo "[$(date +%H:%M:%S)] alive=$alive target=$TARGET; need=$need"
    for slot in "${SLOTS[@]}"; do
      read -r wid wt deployment <<< "$slot"
      if is_alive "$wid"; then
        continue
      fi
      "$PYTHON_BIN" "$REPO_ROOT/tools/chapter_queue.py" release --phase "$PHASE" --worker-id "$wid" >/dev/null
      spawn_slot "$wid" "$wt" "$deployment"
      need=$((need - 1))
      [[ $need -le 0 ]] && break
      sleep "$SPAWN_STAGGER_SECONDS"
    done
  fi
  sleep "$CHECK_INTERVAL_SECONDS"
done
