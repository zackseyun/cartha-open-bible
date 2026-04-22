#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CONCURRENCY="${CONCURRENCY:-2}"
MAX_RETRIES="${MAX_RETRIES:-3}"
MODEL="${MODEL:-gpt-5.4}"
TEMPERATURE="${TEMPERATURE:-0.2}"
LOG_DIR="${LOG_DIR:-/tmp/cartha-enoch-draft}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <chapter> [chapter ...]"
  echo "Example: $0 11 40 72 100"
  exit 2
fi

# Load Azure secret the same way the rest of the repo does.
secret_json="$(aws secretsmanager get-secret-value \
  --secret-id cartha-azure-openai-key --region us-west-2 \
  --query SecretString --output text)"

export AZURE_OPENAI_API_KEY="$(python3 - <<'PY' "$secret_json"
import json,sys
print(json.loads(sys.argv[1])['api_key'])
PY
)"
export AZURE_OPENAI_ENDPOINT="$(python3 - <<'PY' "$secret_json"
import json,sys
print(json.loads(sys.argv[1]).get('endpoint','https://eastus2.api.cognitive.microsoft.com/'))
PY
)"
export AZURE_OPENAI_DEPLOYMENT_ID="$(python3 - <<'PY' "$secret_json"
import json,sys
print(json.loads(sys.argv[1]).get('deployment_name','gpt-5-4-deployment'))
PY
)"
export AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-04-01-preview}"

export REPO_ROOT MODEL TEMPERATURE MAX_RETRIES LOG_DIR PYTHON_BIN DRY_RUN

QUEUE="$($PYTHON_BIN - <<'PY' "$REPO_ROOT" "$@"
import os, sys, pathlib
repo = pathlib.Path(sys.argv[1])
chapters = [int(x) for x in sys.argv[2:]]
sys.path.insert(0, str(repo / 'tools' / 'enoch'))
import verse_parser  # type: ignore
for chapter in chapters:
    rows, warnings = verse_parser.parse_chapter(chapter)
    if warnings:
        for warning in warnings:
            print(f'# warning ch{chapter}: {warning}')
    for row in rows:
        out = repo / 'translation' / 'extra_canonical' / '1_enoch' / f'{chapter:03d}' / f'{row.verse:03d}.yaml'
        if not out.exists():
            print(f'{chapter} {row.verse}')
PY
)"

TASKS="$(printf '%s\n' "$QUEUE" | sed '/^#/d;/^$/d')"
if [[ -z "${TASKS//[$'\n\r\t ']}" ]]; then
  echo "No missing 1 Enoch verses for the requested chapter(s)."
  exit 0
fi

TASK_COUNT="$(printf '%s\n' "$TASKS" | wc -l | tr -d ' ')"
echo "Queueing $TASK_COUNT missing 1 Enoch verse(s)."
if [[ "$DRY_RUN" == "1" ]]; then
  printf '%s\n' "$TASKS"
  exit 0
fi

printf '%s\n' "$TASKS" | xargs -n2 -P "$CONCURRENCY" -I{} bash -lc '
  chapter="$1"
  verse="$2"
  log="$LOG_DIR/ch$(printf "%03d" "$chapter")_v$(printf "%03d" "$verse").log"
  attempt=1
  while (( attempt <= MAX_RETRIES )); do
    echo "[1 Enoch $chapter:$verse] attempt $attempt/$MAX_RETRIES $(date -u +%FT%TZ)" >> "$log"
    if "$PYTHON_BIN" "$REPO_ROOT/tools/enoch/draft.py" --chapter "$chapter" --verse "$verse" --model "$MODEL" --temperature "$TEMPERATURE" >> "$log" 2>&1; then
      echo "[1 Enoch $chapter:$verse] success" >> "$log"
      exit 0
    fi
    sleep_secs=$(( attempt * 15 ))
    echo "[1 Enoch $chapter:$verse] failed; sleeping ${sleep_secs}s before retry" >> "$log"
    sleep "$sleep_secs"
    attempt=$((attempt + 1))
  done
  echo "[1 Enoch $chapter:$verse] exhausted retries" >> "$log"
  exit 1
' _
