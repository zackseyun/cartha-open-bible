#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WORKERS="${WORKERS:-10}"
BACKEND="${BACKEND:-vertex}"
SECRET_IDS="${SECRET_IDS:-/cartha/openclaw/gemini_api_key_2}"
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/refresh_book_summaries.sh <BOOK LABEL> [--chapters-only] [--workers N] [--dry-run]

Examples:
  scripts/refresh_book_summaries.sh "1 ENOCH"
  scripts/refresh_book_summaries.sh "SHEPHERD OF HERMAS" --workers 20
  scripts/refresh_book_summaries.sh "1 ENOCH" --chapters-only

Notes:
- This force-refreshes the summary cache for one book even if summaries already exist.
- Preferred times to run it: after significant wording changes, and especially after
  a second-pass or third-pass revision for that book.
EOF
}

if [[ $# -gt 0 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

BOOK="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --chapters-only)
      EXTRA_ARGS+=(--chapters-only)
      shift
      ;;
    --workers)
      WORKERS="${2:?--workers requires a value}"
      shift 2
      ;;
    --dry-run)
      EXTRA_ARGS+=(--dry-run)
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$REPO_ROOT"

cmd=(
  "$PYTHON_BIN"
  tools/gemini_summary_prewarm.py
  --backend "$BACKEND"
  --workers "$WORKERS"
  --secret-ids "$SECRET_IDS"
  --book "$BOOK"
  --force-refresh
)
if (( ${#EXTRA_ARGS[@]} )); then
  cmd+=("${EXTRA_ARGS[@]}")
fi

exec "${cmd[@]}"
