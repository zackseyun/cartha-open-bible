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
TARGET="${TARGET:-60}"
STOP_FLAG="/tmp/cob-gemini-stop"
LOG_DIR="/tmp/cob-gemini-review"
KEY_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/cartha/gemini-vertex-sa.json}"
GEMINI_SECRET_ID="${GEMINI_SECRET_ID:-/cartha/openclaw/gemini_api_key}"
VERTEX_SECRET_IDS="${VERTEX_SECRET_IDS:-}"
VERTEX_SECRET_DIR="${VERTEX_SECRET_DIR:-/tmp/cob-gemini-vertex-creds}"
CHECK_INTERVAL_SECONDS=30
MAX_SPAWN_PER_CYCLE="${MAX_SPAWN_PER_CYCLE:-10}"
SPAWN_STAGGER_SECONDS="${SPAWN_STAGGER_SECONDS:-3}"
WORKER_SLEEP_SECONDS="${WORKER_SLEEP_SECONDS:-0.75}"
LOCATION_MODE="${LOCATION_MODE:-global}"
PROVIDER_MODE="${PROVIDER_MODE:-aistudio}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-pro-preview}"

REGIONS=(us-central1 us-east1 us-west1 us-west4 europe-west4)
declare -a GEMINI_KEYS=()
declare -a VERTEX_KEY_PATHS=()

mkdir -p "$LOG_DIR"
mkdir -p "$VERTEX_SECRET_DIR"
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

load_api_keys() {
  if (( ${#GEMINI_KEYS[@]} > 0 )); then
    return 0
  fi
  local raw
  local parsed
  raw="$(aws secretsmanager get-secret-value \
    --secret-id "$GEMINI_SECRET_ID" --region us-west-2 \
    --query SecretString --output text)"
  parsed="$(printf '%s' "$raw" | python3 -c '
import sys, json
raw = sys.stdin.read().strip()
keys = []
if not raw:
    raise SystemExit(0)
try:
    obj = json.loads(raw)
except Exception:
    keys = [raw]
else:
    if isinstance(obj, dict):
        if isinstance(obj.get("api_keys"), list):
            keys.extend(str(x).strip() for x in obj["api_keys"] if str(x).strip())
        for k in ("api_key", "apiKey", "key", "GEMINI_API_KEY"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                keys.append(v.strip())
                break
    elif isinstance(obj, list):
        keys.extend(str(x).strip() for x in obj if str(x).strip())
seen = set()
for k in keys:
    if k and k not in seen:
        seen.add(k)
        print(k)
'
  )"
  while IFS= read -r line; do
    [[ -n "$line" ]] && GEMINI_KEYS+=("$line")
  done <<< "$parsed"
  if (( ${#GEMINI_KEYS[@]} == 0 )); then
    echo "no Gemini API keys resolved from $GEMINI_SECRET_ID" >&2
    return 1
  fi
}

selected_api_key() {
  local wid="$1"
  local idx=$(( (wid - 1) % ${#GEMINI_KEYS[@]} ))
  printf '%s' "${GEMINI_KEYS[$idx]}"
}

load_vertex_key_paths() {
  if (( ${#VERTEX_KEY_PATHS[@]} > 0 )); then
    return 0
  fi
  if [[ -f "$KEY_PATH" ]]; then
    VERTEX_KEY_PATHS+=("$KEY_PATH")
  fi
  local secret_id
  IFS=',' read -r -a _secret_ids <<< "$VERTEX_SECRET_IDS"
  for secret_id in "${_secret_ids[@]}"; do
    secret_id="${secret_id//[[:space:]]/}"
    [[ -z "$secret_id" ]] && continue
    local slug
    local out
    slug="$(printf '%s' "$secret_id" | tr '/:' '__')"
    out="$VERTEX_SECRET_DIR/${slug}.json"
    if [[ ! -f "$out" ]]; then
      aws secretsmanager get-secret-value \
        --secret-id "$secret_id" --region us-west-2 \
        --query SecretString --output text > "$out"
      chmod 600 "$out"
    fi
    VERTEX_KEY_PATHS+=("$out")
  done
  # de-dupe while preserving order
  local deduped=()
  local seen=""
  local p
  for p in "${VERTEX_KEY_PATHS[@]}"; do
    [[ -z "$p" ]] && continue
    if [[ " $seen " == *" $p "* ]]; then
      continue
    fi
    seen="$seen $p"
    deduped+=("$p")
  done
  VERTEX_KEY_PATHS=("${deduped[@]}")
  if (( ${#VERTEX_KEY_PATHS[@]} == 0 )); then
    echo "no Vertex credential paths resolved (KEY_PATH=$KEY_PATH, VERTEX_SECRET_IDS=$VERTEX_SECRET_IDS)" >&2
    return 1
  fi
}

selected_vertex_key_path() {
  local wid="$1"
  local idx=$(( (wid - 1) % ${#VERTEX_KEY_PATHS[@]} ))
  printf '%s' "${VERTEX_KEY_PATHS[$idx]}"
}

requeue_failed() {
  python3 "$REPO_ROOT/tools/gemini_review_queue.py" requeue >/dev/null 2>&1 || true
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
  if [[ "$PROVIDER_MODE" == "aistudio" ]]; then
    load_api_keys
    local api_key
    local key_slot
    api_key="$(selected_api_key "$wid")"
    key_slot=$(( ((wid - 1) % ${#GEMINI_KEYS[@]}) + 1 ))
    nohup env \
      GOOGLE_APPLICATION_CREDENTIALS="" \
      GEMINI_API_KEY="$api_key" \
      GCP_LOCATION="global" \
      python3 "$REPO_ROOT/tools/gemini_review_worker.py" \
        --worker-id "w$wid" \
        --model-override "$GEMINI_MODEL" \
        --max-jobs 100000 \
        --sleep "$WORKER_SLEEP_SECONDS" \
      > "$LOG_DIR/worker-w$wid.log" 2>&1 &
    echo "  spawned w$wid @ global (aistudio key ${key_slot}/${#GEMINI_KEYS[@]} model=$GEMINI_MODEL)"
  elif [[ "$PROVIDER_MODE" == "vertex_pool" ]]; then
    load_vertex_key_paths
    local vertex_key_path
    local key_slot
    vertex_key_path="$(selected_vertex_key_path "$wid")"
    key_slot=$(( ((wid - 1) % ${#VERTEX_KEY_PATHS[@]}) + 1 ))
    nohup env \
      GOOGLE_APPLICATION_CREDENTIALS="$vertex_key_path" \
      GCP_LOCATION="$location" \
      python3 "$REPO_ROOT/tools/gemini_review_worker.py" \
        --worker-id "w$wid" \
        --model-override "$GEMINI_MODEL" \
        --max-jobs 100000 \
        --sleep "$WORKER_SLEEP_SECONDS" \
      > "$LOG_DIR/worker-w$wid.log" 2>&1 &
    echo "  spawned w$wid @ $location (vertex key ${key_slot}/${#VERTEX_KEY_PATHS[@]} model=$GEMINI_MODEL)"
  else
    nohup env \
      GOOGLE_APPLICATION_CREDENTIALS="$KEY_PATH" \
      GCP_LOCATION="$location" \
      python3 "$REPO_ROOT/tools/gemini_review_worker.py" \
        --worker-id "w$wid" \
        --model-override "$GEMINI_MODEL" \
        --max-jobs 100000 \
        --sleep "$WORKER_SLEEP_SECONDS" \
      > "$LOG_DIR/worker-w$wid.log" 2>&1 &
    echo "  spawned w$wid @ $location (vertex model=$GEMINI_MODEL)"
  fi
}

echo "[$(date +%H:%M:%S)] supervise_gemini_workers starting; target=$TARGET"
echo "   stop with: touch $STOP_FLAG"
echo "   provider_mode=$PROVIDER_MODE model=$GEMINI_MODEL location_mode=$LOCATION_MODE stagger=${SPAWN_STAGGER_SECONDS}s max_spawn_per_cycle=$MAX_SPAWN_PER_CYCLE"

while true; do
  if [[ -f "$STOP_FLAG" ]]; then
    echo "[$(date +%H:%M:%S)] stop flag present; exiting (existing workers keep running)"
    rm -f "$STOP_FLAG"
    exit 0
  fi
  requeue_failed

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
