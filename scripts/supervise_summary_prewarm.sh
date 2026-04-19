#!/usr/bin/env bash
set -euo pipefail

NAME="${1:?name required}"
BOOKS="${2:?books csv required}"
EXTRA_ARGS="${3:-}"
COORD="${COORD:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation}"
APIROOT="${APIROOT:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/CarthaCdkService/services/mobile-api-service-go}"
LOG="/tmp/cob-summary-${NAME}.log"
MAX_RESTARTS="${MAX_RESTARTS:-12}"
RESTART_SLEEP_SECONDS="${RESTART_SLEEP_SECONDS:-60}"

fetch_azure_key() {
  if [[ -z "${AZURE_OPENAI_KEY:-}" ]]; then
    local secret_json
    secret_json="$(aws secretsmanager get-secret-value \
      --secret-id cartha-azure-openai-key \
      --region us-west-2 \
      --query SecretString \
      --output text)"
    export AZURE_OPENAI_KEY="$(python3 - <<'PY' "$secret_json"
import json, sys
print(json.loads(sys.argv[1])["api_key"])
PY
)"
    export AZURE_OPENAI_ENDPOINT="$(python3 - <<'PY' "$secret_json"
import json, sys
print(json.loads(sys.argv[1])["endpoint"])
PY
)"
    export BIBLE_SUMMARY_AZURE_DEPLOYMENT_ID="${BIBLE_SUMMARY_AZURE_DEPLOYMENT_ID:-gpt-5-4-summary-deployment}"
  fi
}

cd "$APIROOT" || exit 2
fetch_azure_key
echo "[summary-supervisor] started name=$NAME books=$BOOKS extra=$EXTRA_ARGS at $(date -u +%FT%TZ)" >> "$LOG"

restarts=0
while :; do
  ./prewarm-bible-summary-cache \
    --translation-repo "$COORD" \
    --stage alpha \
    --translation COB \
    --translation-version unspecified \
    --books "$BOOKS" \
    ${EXTRA_ARGS} >> "$LOG" 2>&1 || true

  restarts=$((restarts + 1))
  if [[ "$restarts" -ge "$MAX_RESTARTS" ]]; then
    echo "[summary-supervisor] name=$NAME reached max restarts, exiting" >> "$LOG"
    exit 0
  fi
  sleep "$RESTART_SLEEP_SECONDS"
done
