#!/usr/bin/env bash
set -euo pipefail

LAMBDA_NAME="${LAMBDA_NAME:-cartha-cob-publisher}"
LOG="${LOG:-/tmp/cob-publish.log}"
RESP="${RESP:-/tmp/cob-publish-response.json}"

echo "[publish] forcing ${LAMBDA_NAME} at $(date -u +%FT%TZ)" >> "$LOG"

aws lambda invoke \
  --function-name "$LAMBDA_NAME" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"force":true}' \
  "$RESP" >> "$LOG" 2>&1

if [[ -f "$RESP" ]]; then
  echo "[publish] response: $(tr '\n' ' ' < "$RESP")" >> "$LOG"
fi
