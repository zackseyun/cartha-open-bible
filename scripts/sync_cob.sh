#!/usr/bin/env bash
# sync_cob.sh — run the full COB publish pipeline once, synchronously.
#
# This is the manual equivalent of what supervise_merge.sh does in a
# loop. Run it whenever you want to push any pending chapter drafts to
# main and force the CDN to re-publish. Exits when done.
#
# Order of operations:
#   1. chapter_merge.py cherry-picks any ready-to-merge jobs onto main
#      and pushes (no-op if the queue is empty).
#   2. publish_cob.sh fires the cartha-cob-publisher Lambda which
#      rebuilds cob_preview.json from main and uploads to
#      bible.cartha.com. (Forces re-publish even if step 1 was a no-op,
#      so a CDN that has drifted behind main still gets corrected.)
#   3. Prints the resulting CDN manifest so you can see what landed.
#
# Exit status: 0 on successful publish; non-zero on any failure.
#
# Usage:
#   scripts/sync_cob.sh                 # full pipeline
#   scripts/sync_cob.sh --publish-only  # skip the merge step
#   scripts/sync_cob.sh --merge-only    # skip the publish step

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COORD="$(cd "$SCRIPT_DIR/.." && pwd)"
PUBLISH_ONLY=0
MERGE_ONLY=0
MERGE_LIMIT="${MERGE_LIMIT:-500}"

for arg in "$@"; do
  case "$arg" in
    --publish-only) PUBLISH_ONLY=1 ;;
    --merge-only)   MERGE_ONLY=1 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

say() { printf "\033[1m[sync-cob]\033[0m %s\n" "$*"; }

if [[ "$PUBLISH_ONLY" != "1" ]]; then
  say "merge: cherry-picking any ready-to-merge jobs onto main and pushing"
  cd "$COORD"
  python3 tools/chapter_merge.py --coord-root "$COORD" --limit "$MERGE_LIMIT" --push
fi

if [[ "$MERGE_ONLY" == "1" ]]; then
  say "merge-only requested — skipping publish"
  exit 0
fi

say "publish: invoking cartha-cob-publisher Lambda"
"$SCRIPT_DIR/publish_cob.sh"

# Show what the CDN now reports, for a clean receipt.
say "CDN manifest after publish:"
curl -sL --max-time 15 "https://bible.cartha.com/manifest.json" \
  | python3 -m json.tool 2>/dev/null || {
    echo "  (failed to fetch CDN manifest — publish may still be propagating)"
  }
