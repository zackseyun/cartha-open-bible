#!/usr/bin/env bash
# redraft_thomas_problem_sayings.sh — rerun Gospel of Thomas sayings
# whose Gemini-Pro v3 review gave agreement_score < 0.8, using the
# strict Coptic-aware drafter (Gemini 3.1 Pro cross-family from the
# original Azure GPT-5.4 drafter).
#
# Usage:  scripts/redraft_thomas_problem_sayings.sh [--threshold 0.8] [--dry-run]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$REPO_ROOT/state/chapter_queue.sqlite3"
THRESHOLD="${THRESHOLD:-0.8}"
DRY_RUN=""
LOG_DIR="/tmp/cob-thomas-redraft"
CONCURRENCY="${CONCURRENCY:-3}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN="--dry-run" ;;
    --threshold=*) THRESHOLD="${arg#*=}" ;;
    --threshold) shift; THRESHOLD="$1" ;;
  esac
done

mkdir -p "$LOG_DIR"

# Pull the sayings that need redrafting — agreement < threshold
SAYINGS=$(sqlite3 "$DB" "SELECT verse FROM review_jobs WHERE strategy='phase9_nag_hammadi' AND status='completed' AND agreement_score IS NOT NULL AND agreement_score < $THRESHOLD ORDER BY agreement_score ASC;")
COUNT=$(printf '%s\n' "$SAYINGS" | sed '/^$/d' | wc -l | tr -d ' ')
echo "Found $COUNT Thomas sayings below agreement $THRESHOLD. Redrafting with concurrency=$CONCURRENCY."

cd "$REPO_ROOT"

# Ensure Gemini key in env (draft_gospel_of_thomas.py fetches from AWS if not)
export GEMINI_API_KEY="${GEMINI_API_KEY:-$(aws secretsmanager get-secret-value --secret-id /cartha/openclaw/gemini_api_key --region us-west-2 --query SecretString --output text | python3 -c "import json,sys; raw=sys.stdin.read().strip();
try: print(json.loads(raw).get('api_key', raw))
except: print(raw)")}"

# Run in parallel with xargs — each process handles one saying
printf '%s\n' "$SAYINGS" | sed '/^$/d' | xargs -n1 -P "$CONCURRENCY" -I{} bash -c '
  saying="$1"
  log="$LOG_DIR/saying$(printf "%03d" "$saying").log"
  echo "[saying $saying] starting $(date -u +%FT%TZ)" >> "$log"
  if python3 '"$REPO_ROOT"'/tools/draft_gospel_of_thomas.py --saying "$saying" '"$DRY_RUN"' >> "$log" 2>&1; then
    echo "[saying $saying] OK" >> "$log"
  else
    echo "[saying $saying] FAILED (exit=$?)" >> "$log"
  fi
' -- {} "$LOG_DIR"

echo "Done. Logs in $LOG_DIR/"
