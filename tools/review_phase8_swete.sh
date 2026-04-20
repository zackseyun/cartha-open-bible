#!/usr/bin/env bash
# review_phase8_swete.sh — launch the Azure GPT-5.4 reviewer across the
# entire Phase 8 Swete deuterocanonical corpus.
#
# This mirrors the original transcription batching style, but uses the
# corrections-only reviewer (`tools/review_transcription.py`) instead of a
# fresh transcription pass.
#
# Default scope (572 pages total):
#   vol 2: 148-192,626-862
#   vol 3: 379-398,542-790,895-915
#
# Examples:
#   tools/review_phase8_swete.sh
#   tools/review_phase8_swete.sh --concurrency 6 --logs-dir state/review_logs
#   tools/review_phase8_swete.sh --dry-run
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONCURRENCY=6
DEPLOYMENT="gpt-5-4-deployment"
SKIP_EXISTING=1
DRY_RUN=0
LOGS_DIR="$REPO_ROOT/state/review_logs"
VOL2_PAGES="148-192,626-862"
VOL3_PAGES="379-398,542-790,895-915"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --logs-dir) LOGS_DIR="$2"; shift 2 ;;
    --deployment) DEPLOYMENT="$2"; shift 2 ;;
    --no-skip-existing) SKIP_EXISTING=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# //' 
      exit 0
      ;;
    *)
      echo "unknown flag: $1" >&2
      exit 2
      ;;
  esac
done

fetch_azure_env() {
  if [[ -n "${AZURE_OPENAI_API_KEY:-}" && -n "${AZURE_OPENAI_ENDPOINT:-}" ]]; then
    export AZURE_OPENAI_DEPLOYMENT_ID="${AZURE_OPENAI_DEPLOYMENT_ID:-$DEPLOYMENT}"
    export AZURE_OPENAI_VISION_DEPLOYMENT_ID="${AZURE_OPENAI_VISION_DEPLOYMENT_ID:-${AZURE_OPENAI_DEPLOYMENT_ID}}"
    export AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-04-01-preview}"
    return 0
  fi

  local secret_json
  secret_json=$(aws secretsmanager get-secret-value \
    --secret-id cartha-azure-openai-key \
    --region us-west-2 \
    --query SecretString \
    --output text)

  export AZURE_OPENAI_API_KEY
  AZURE_OPENAI_API_KEY=$(python3 - <<'PY' "$secret_json"
import json,sys
print(json.loads(sys.argv[1])['api_key'])
PY
)

  export AZURE_OPENAI_ENDPOINT
  AZURE_OPENAI_ENDPOINT=$(python3 - <<'PY' "$secret_json"
import json,sys
obj=json.loads(sys.argv[1])
print(obj.get('endpoint') or 'https://eastus2.api.cognitive.microsoft.com')
PY
)

  export AZURE_OPENAI_DEPLOYMENT_ID="$DEPLOYMENT"
  export AZURE_OPENAI_VISION_DEPLOYMENT_ID="$DEPLOYMENT"
  export AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-04-01-preview}"
}

mkdir -p "$LOGS_DIR"
fetch_azure_env
VOL2_LOG="$LOGS_DIR/review_phase8_vol2.log"
VOL3_LOG="$LOGS_DIR/review_phase8_vol3.log"

skip_flag=()
if [[ "$SKIP_EXISTING" == 1 ]]; then
  skip_flag+=(--skip-existing)
fi

LAST_PID=""

dispatch() {
  local vol="$1"
  local pages="$2"
  local log_file="$3"
  local cmd=(python3 "$REPO_ROOT/tools/review_transcription.py" --vol "$vol" --pages "$pages" --concurrency "$CONCURRENCY")
  cmd+=("${skip_flag[@]}")
  if [[ "$DRY_RUN" == 1 ]]; then
    cmd+=(--dry-run)
    printf '[dry-run]'
    printf ' %q' "${cmd[@]}"
    printf '\n'
    return 0
  fi
  echo "=== launching vol ${vol} review (${pages}) ===" | tee -a "$log_file"
  nohup "${cmd[@]}" >>"$log_file" 2>&1 &
  LAST_PID=$!
}

if [[ "$DRY_RUN" == 1 ]]; then
  dispatch 2 "$VOL2_PAGES" "$VOL2_LOG"
  dispatch 3 "$VOL3_PAGES" "$VOL3_LOG"
  exit 0
fi

dispatch 2 "$VOL2_PAGES" "$VOL2_LOG"
v2_pid="$LAST_PID"
dispatch 3 "$VOL3_PAGES" "$VOL3_LOG"
v3_pid="$LAST_PID"

echo "launched Azure review workers:"
echo "  deployment=$AZURE_OPENAI_DEPLOYMENT_ID endpoint=$AZURE_OPENAI_ENDPOINT concurrency_per_vol=$CONCURRENCY"
echo "  vol2 pid=$v2_pid log=$VOL2_LOG"
echo "  vol3 pid=$v3_pid log=$VOL3_LOG"
echo "tail logs with:"
echo "  tail -f '$VOL2_LOG' '$VOL3_LOG'"
