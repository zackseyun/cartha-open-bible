#!/usr/bin/env bash
# opus_review_transcription.sh — Run Claude Opus 4.7 (via Claude Code
# headless `claude -p`) as a cross-model reviewer over transcribed
# Swete pages. For each page: fetches the archive.org scan to /tmp,
# feeds it + the existing transcript + tools/prompts/review_greek_swete.md
# to Opus, saves the JSON review alongside the transcription as
# <stem>.opus-review.json.
#
# Uses the local Claude Code subscription for token cost. No Anthropic
# API key required.
#
# Usage:
#   tools/opus_review_transcription.sh --vol 2 --pages 626-665 [--concurrency 3]
#   tools/opus_review_transcription.sh --vol 3 --pages 379-398,542-597
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT_FILE="${REPO_ROOT}/tools/prompts/review_greek_swete.md"
TRANSCRIBED_DIR="${REPO_ROOT}/sources/lxx/swete/transcribed"
IMG_DIR="/tmp/opus_review_imgs"
mkdir -p "$IMG_DIR"

SWETE_ITEM="theoldtestamenti03swetuoft_202003"
vol_basename() {
  case "$1" in
    1) echo "oldtestamentingr01swet" ;;
    2) echo "oldtestamentingr02swet" ;;
    3) echo "theoldtestamenti03swetuoft" ;;
    *) return 1 ;;
  esac
}

VOL=""
PAGES_SPEC=""
CONCURRENCY=3
SKIP_EXISTING=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vol) VOL="$2"; shift 2 ;;
    --page) PAGES_SPEC="$2"; shift 2 ;;
    --pages) PAGES_SPEC="$2"; shift 2 ;;
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --no-skip-existing) SKIP_EXISTING=0; shift ;;
    -h|--help) grep -E "^# " "$0" | sed 's/^# //' ; exit 0 ;;
    *) echo "unknown flag: $1" >&2 ; exit 2 ;;
  esac
done
[[ -z "$VOL" ]] && { echo "missing --vol" >&2 ; exit 2 ; }
[[ -z "$PAGES_SPEC" ]] && { echo "missing --pages" >&2 ; exit 2 ; }
[[ -f "$PROMPT_FILE" ]] || { echo "missing prompt file $PROMPT_FILE" >&2 ; exit 2 ; }

# expand "1-5,8,10-12" into a space-separated page list
expand_pages() {
  local spec="$1"
  IFS=',' read -ra parts <<< "$spec"
  for p in "${parts[@]}"; do
    if [[ "$p" == *-* ]]; then
      local a="${p%-*}" b="${p#*-}"
      seq "$a" "$b"
    else
      echo "$p"
    fi
  done
}

PAGES=( $(expand_pages "$PAGES_SPEC") )

fetch_image() {
  local page="$1"
  local img="$IMG_DIR/vol${VOL}_p$(printf %04d $page).jpg"
  if [[ -s "$img" ]]; then echo "$img"; return 0; fi
  local basename
  basename=$(vol_basename "$VOL") || return 1
  local url="https://archive.org/download/${SWETE_ITEM}/${basename}/page/n${page}_w1500.jpg"
  curl -sL --user-agent "cartha-open-bible/1.0" -o "$img" "$url" || { rm -f "$img"; return 1; }
  [[ -s "$img" ]] || { rm -f "$img"; return 1; }
  echo "$img"
}

review_page() {
  local page="$1"
  local stem="vol${VOL}_p$(printf %04d $page)"
  local tf="${TRANSCRIBED_DIR}/${stem}.txt"
  local out="${TRANSCRIBED_DIR}/${stem}.opus-review.json"
  if [[ "$SKIP_EXISTING" == 1 && -s "$out" ]]; then
    echo "  SKIP ${stem} (already reviewed)" >&2
    return 0
  fi
  [[ -f "$tf" ]] || { echo "  MISS ${stem} no transcript" >&2; return 1; }
  local img
  img=$(fetch_image "$page") || { echo "  FAIL ${stem} image fetch" >&2; return 1; }
  local user_prompt="Review the transcription below against the Swete LXX page image at ${img}. Read the image via your Read tool. Return ONLY the JSON object per the system prompt.

===EXISTING TRANSCRIPTION===
$(cat "$tf")
===END TRANSCRIPTION==="
  local t0=$(date +%s)
  claude --model claude-opus-4-7 \
    --add-dir "$IMG_DIR" \
    --allowedTools Read \
    --append-system-prompt "$(cat "$PROMPT_FILE")" \
    -p "$user_prompt" < /dev/null > "$out" 2>/dev/null || {
      echo "  FAIL ${stem} claude -p exit $?" >&2
      return 1
    }
  local dt=$(($(date +%s) - t0))
  local sz=$(wc -c < "$out" | tr -d ' ')
  echo "  OK   ${stem}  ${dt}s  ${sz} bytes" >&2
}

export -f fetch_image review_page expand_pages vol_basename
export VOL PAGES_SPEC CONCURRENCY SKIP_EXISTING
export REPO_ROOT PROMPT_FILE TRANSCRIBED_DIR IMG_DIR SWETE_ITEM

echo "=== Opus cross-read  vol ${VOL}  ${#PAGES[@]} pages  concurrency ${CONCURRENCY} ===" >&2
start=$(date +%s)
if [[ "$CONCURRENCY" == 1 ]]; then
  for pg in "${PAGES[@]}"; do review_page "$pg"; done
else
  # Emit pages through xargs -P for parallel
  printf '%s\n' "${PAGES[@]}" | xargs -n 1 -P "$CONCURRENCY" -I{} bash -c 'review_page "$@"' _ {}
fi
echo "=== done in $(($(date +%s) - start))s ===" >&2
