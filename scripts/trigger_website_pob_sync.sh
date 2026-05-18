#!/usr/bin/env bash
# trigger_website_pob_sync.sh — after bible.cartha.com publishes a new POB
# manifest, start the cartha.website pipeline so the same-origin static
# /bibles/pob/* bundle is rebuilt from that exact upstream version.

set -euo pipefail

if [[ "${POB_SKIP_WEBSITE_SYNC:-0}" == "1" ]]; then
  echo "[website-sync] skipped because POB_SKIP_WEBSITE_SYNC=1"
  exit 0
fi

WEBSITE_PIPELINE_NAME="${WEBSITE_PIPELINE_NAME:-cartha-website-pipeline}"
WEBSITE_PIPELINE_REGION="${WEBSITE_PIPELINE_REGION:-us-west-2}"
CDN_MANIFEST_URL="${CDN_MANIFEST_URL:-https://bible.cartha.com/manifest.json}"
MANIFEST_WAIT_ATTEMPTS="${POB_MANIFEST_WAIT_ATTEMPTS:-30}"
MANIFEST_WAIT_SECONDS="${POB_MANIFEST_WAIT_SECONDS:-10}"
PIPELINE_IDLE_ATTEMPTS="${POB_WEBSITE_PIPELINE_IDLE_ATTEMPTS:-60}"
PIPELINE_IDLE_SECONDS="${POB_WEBSITE_PIPELINE_IDLE_SECONDS:-10}"

say() { printf '[website-sync] %s\n' "$*"; }

resolve_target_sha() {
  if [[ -n "${TARGET_SHA:-}" ]]; then
    printf '%s\n' "$TARGET_SHA"
    return 0
  fi
  if [[ -n "${CODEBUILD_RESOLVED_SOURCE_VERSION:-}" ]]; then
    printf '%s\n' "$CODEBUILD_RESOLVED_SOURCE_VERSION"
    return 0
  fi
  if command -v git >/dev/null 2>&1; then
    git ls-remote origin refs/heads/main 2>/dev/null | awk 'NR==1 {print $1; exit}' && return 0
    git rev-parse origin/main 2>/dev/null && return 0
    git rev-parse HEAD 2>/dev/null && return 0
  fi
  return 1
}

TARGET_SHA_RESOLVED="$(resolve_target_sha || true)"
if [[ -n "$TARGET_SHA_RESOLVED" ]]; then
  say "waiting for CDN manifest to reach $TARGET_SHA_RESOLVED"
  matched=0
  for i in $(seq 1 "$MANIFEST_WAIT_ATTEMPTS"); do
    BODY="$(curl -fsSL --max-time 15 "$CDN_MANIFEST_URL" || true)"
    SHA=""
    VERSION=""
    if [[ -n "$BODY" ]]; then
      SHA="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("commit_sha") or "")' <<<"$BODY" 2>/dev/null || true)"
      VERSION="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("version") or "")' <<<"$BODY" 2>/dev/null || true)"
    fi
    say "attempt=$i manifest_sha=${SHA:-missing} version=${VERSION:-missing}"
    if [[ "$SHA" == "$TARGET_SHA_RESOLVED" ]]; then
      matched=1
      break
    fi
    sleep "$MANIFEST_WAIT_SECONDS"
  done
  if [[ "$matched" != "1" ]]; then
    echo "[website-sync] CDN manifest did not reach $TARGET_SHA_RESOLVED; refusing to trigger stale website sync" >&2
    exit 1
  fi
else
  say "target SHA unavailable; triggering website pipeline without manifest SHA gate"
fi

pipeline_busy() {
  aws codepipeline get-pipeline-state \
    --region "$WEBSITE_PIPELINE_REGION" \
    --name "$WEBSITE_PIPELINE_NAME" \
    --query 'stageStates[].latestExecution.status' \
    --output text 2>/dev/null | grep -qw InProgress
}

for i in $(seq 1 "$PIPELINE_IDLE_ATTEMPTS"); do
  if ! pipeline_busy; then
    break
  fi
  say "website pipeline already in progress; waiting before starting a fresh post-POB run ($i/$PIPELINE_IDLE_ATTEMPTS)"
  sleep "$PIPELINE_IDLE_SECONDS"
done

if pipeline_busy; then
  echo "[website-sync] website pipeline is still busy; refusing to claim the POB website bundle is refreshed" >&2
  exit 1
fi

EXECUTION_ID="$(aws codepipeline start-pipeline-execution \
  --region "$WEBSITE_PIPELINE_REGION" \
  --name "$WEBSITE_PIPELINE_NAME" \
  --query 'pipelineExecutionId' \
  --output text)"

say "started $WEBSITE_PIPELINE_NAME in $WEBSITE_PIPELINE_REGION (execution $EXECUTION_ID)"
