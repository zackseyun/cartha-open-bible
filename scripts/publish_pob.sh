#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAMBDA_NAME="${LAMBDA_NAME:-cartha-cob-publisher}"
LOG="${LOG:-/tmp/pob-publish.log}"
RESP="${RESP:-/tmp/pob-publish-response.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[publish] forcing ${LAMBDA_NAME} at $(date -u +%FT%TZ)" >> "$LOG"

if [[ "${POB_SKIP_READER_VALIDATION:-0}" != "1" ]]; then
  echo "[publish] validating reader corpus before Lambda invoke" | tee -a "$LOG"
  "$PYTHON_BIN" "$REPO_ROOT/tools/validate_reader_corpus.py" --quiet --malformed-yaml warn 2>&1 | tee -a "$LOG"
fi

aws lambda invoke \
  --function-name "$LAMBDA_NAME" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"force":true}' \
  --cli-read-timeout 300 \
  --region us-west-2 \
  "$RESP" >> "$LOG" 2>&1

if [[ -f "$RESP" ]]; then
  echo "[publish] response: $(tr '\n' ' ' < "$RESP")" >> "$LOG"
fi

if [[ "${POB_SKIP_WEBSITE_SYNC:-0}" != "1" ]]; then
  echo "[publish] triggering website POB bundle sync" | tee -a "$LOG"
  "$SCRIPT_DIR/trigger_website_pob_sync.sh" 2>&1 | tee -a "$LOG"
fi
