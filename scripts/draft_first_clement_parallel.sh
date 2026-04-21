#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation}"
CONCURRENCY="${CONCURRENCY:-2}"
MAX_RETRIES="${MAX_RETRIES:-4}"
MODEL="${MODEL:-gpt-5.4}"
TEMPERATURE="${TEMPERATURE:-0.2}"
LOG_DIR="${LOG_DIR:-/tmp/cartha-first-clement-draft}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

export AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-$(aws secretsmanager get-secret-value --secret-id cartha-azure-openai-key --region us-west-2 --query SecretString --output text | python3 -c "import json,sys; print(json.load(sys.stdin)['api_key'])")}"
export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-https://eastus2.api.cognitive.microsoft.com}"
export AZURE_OPENAI_DEPLOYMENT_ID="${AZURE_OPENAI_DEPLOYMENT_ID:-gpt-5-4-deployment}"
export AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-04-01-preview}"

CHAPTER_LIST="$(python3 - <<'PY'
from pathlib import Path
root = Path('/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation/translation/extra_canonical/1_clement')
existing = {int(p.stem) for p in root.glob('*.yaml')}
for ch in range(1, 66):
    if ch not in existing:
        print(ch)
PY
)"

if [[ -z "${CHAPTER_LIST//[$'\n\r\t ']}" ]]; then
  echo "No missing 1 Clement chapters to draft."
  exit 0
fi

CHAPTER_COUNT="$(printf '%s\n' "$CHAPTER_LIST" | sed '/^$/d' | wc -l | tr -d ' ')"
printf 'Queueing %s missing 1 Clement chapter(s): %s\n' "$CHAPTER_COUNT" "$(printf '%s ' $CHAPTER_LIST)"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

export REPO_ROOT MODEL TEMPERATURE MAX_RETRIES LOG_DIR PYTHON_BIN

printf '%s\n' "$CHAPTER_LIST" | sed '/^$/d' | xargs -n1 -P "$CONCURRENCY" -I{} bash -lc '
  ch="$1"
  log="$LOG_DIR/ch$(printf "%03d" "$ch").log"
  attempt=1
  while (( attempt <= MAX_RETRIES )); do
    echo "[chapter $ch] attempt $attempt/{$MAX_RETRIES} $(date -u +%FT%TZ)" >> "$log"
    if "$PYTHON_BIN" "$REPO_ROOT/tools/draft_first_clement.py" --chapter "$ch" --model "$MODEL" --temperature "$TEMPERATURE" >> "$log" 2>&1; then
      echo "[chapter $ch] success" >> "$log"
      exit 0
    fi
    sleep_secs=$(( attempt * 15 ))
    echo "[chapter $ch] failed; sleeping ${sleep_secs}s before retry" >> "$log"
    sleep "$sleep_secs"
    attempt=$((attempt + 1))
  done
  echo "[chapter $ch] exhausted retries" >> "$log"
  exit 1
' _ {}
