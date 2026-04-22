#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation}"
CONCURRENCY="${CONCURRENCY:-10}"
MAX_RETRIES="${MAX_RETRIES:-4}"
LOG_DIR="${LOG_DIR:-/tmp/cartha-jubilees-review}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

CHAPTER_LIST="$(python3 - <<'PY'
from pathlib import Path
import yaml
import os
root = Path(os.environ['REPO_ROOT']) / 'translation' / 'extra_canonical' / 'jubilees'
for ch in range(1, 51):
    path = root / f'{ch:03d}.yaml'
    if not path.exists():
        continue
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    reviews = doc.get('review_passes') or []
    if reviews:
        continue
    print(ch)
PY
)"

if [[ -z "${CHAPTER_LIST//[$'\n\r\t ']}" ]]; then
  echo "No unrevised Jubilees chapters to review."
  exit 0
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

export REPO_ROOT MAX_RETRIES LOG_DIR PYTHON_BIN

printf '%s\n' "$CHAPTER_LIST" | sed '/^$/d' | xargs -n1 -P "$CONCURRENCY" -I{} bash -lc '
  ch="$1"
  log="$LOG_DIR/ch$(printf "%03d" "$ch").log"
  attempt=1
  while (( attempt <= MAX_RETRIES )); do
    echo "[chapter $ch] review attempt $attempt/$MAX_RETRIES $(date -u +%FT%TZ)" >> "$log"
    if "$PYTHON_BIN" "$REPO_ROOT/tools/jubilees/review_chapter.py" --chapter "$ch" >> "$log" 2>&1; then
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
