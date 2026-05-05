#!/usr/bin/env bash
# cob-revisions-flywheel.sh
#
# Local flywheel that keeps the Cartha Open Bible public revisions
# index honest. Walks both the YAML revision history (verses where an
# applied edit was committed) AND the local state/reviews/ tree (every
# verse-level review pass that ran, including "agree" verdicts where
# no edit was applied), then commits revisions.json + pushes if the
# numbers changed.
#
# Why local: state/ is gitignored — the 50k+ review records exist only
# on this Mac. GitHub Actions can only see committed YAML, which makes
# the public count look like ~9% of work done when it's actually
# ~100%. Running this from a launchd job (StartInterval=1800) means
# the public dashboard is at most 30 minutes behind reality without
# us bloating the repo with the raw review payloads.
#
# Companion launchd plist:
#   ~/Library/LaunchAgents/com.cartha.cob-revisions-flywheel.plist
#
# Manual one-shot:  bash ~/scripts/cob-revisions-flywheel.sh
# Tail logs:        tail -f /tmp/cob-revisions-flywheel-stdout.log

set -u

REPO="/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation"
# Homebrew python3 has PyYAML; the system /usr/bin/python3 does not.
PYTHON="/opt/homebrew/bin/python3"
LOG_PREFIX="[$(date -u +%FT%TZ)]"

# Make sure git can reach the keychain ssh key when run under launchd
# (launchd has a minimal env — explicitly point at the user's ssh agent).
if [ -z "${SSH_AUTH_SOCK:-}" ]; then
  candidate=$(ls -1t /private/tmp/com.apple.launchd.*/Listeners 2>/dev/null | head -n1 || true)
  if [ -n "$candidate" ]; then
    export SSH_AUTH_SOCK="$candidate"
  fi
fi
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd "$REPO" || { echo "$LOG_PREFIX repo not found at $REPO"; exit 1; }

# Don't fight a long-running drafter holding the index open in another
# checkout. If anything's writing to state/reviews/ in the last 60s,
# defer — the launchd reschedule will catch the next window.
recent_writes=$(find state/reviews -type f -mtime -1m 2>/dev/null | head -1)
if [ -n "${recent_writes:-}" ]; then
  echo "$LOG_PREFIX defer: review records being written, will retry next tick"
  # Not an error — exit clean so launchd doesn't backoff.
  exit 0
fi

echo "$LOG_PREFIX regenerating revisions.json"
if ! "$PYTHON" tools/build_revisions_index.py; then
  echo "$LOG_PREFIX build_revisions_index.py failed"
  exit 1
fi

if git diff --quiet revisions.json; then
  echo "$LOG_PREFIX revisions.json unchanged — nothing to publish"
  exit 0
fi

# Show a one-line summary of what changed for the launchd log.
new_summary=$("$PYTHON" - <<'PY'
import json, pathlib
d = json.loads(pathlib.Path("revisions.json").read_text())
t = d.get("totals", {})
rc = d.get("review_coverage", {})
print(
    f"applied={t.get('total_revisions',0)}/{t.get('verses_with_revisions',0)}v "
    f"reviewed={rc.get('review_passes_total',0)}/{rc.get('verses_reviewed',0)}v"
)
PY
)
echo "$LOG_PREFIX new totals: $new_summary"

git add revisions.json
git commit -m "revisions: regenerate index ($new_summary) [skip ci]" || {
  echo "$LOG_PREFIX commit failed (working tree dirty?)"
  exit 1
}

# regen-status.yml runs hourly on the same repo and pushes status.json,
# so we routinely need to rebase before push. Use rebase --autostash to
# tolerate any other dirty files (untracked files don't trigger autostash).
if ! git pull --rebase --autostash; then
  echo "$LOG_PREFIX rebase failed — leaving local commit, will retry next tick"
  exit 1
fi

if ! git push; then
  echo "$LOG_PREFIX push failed after rebase — leaving local commit, will retry next tick"
  exit 1
fi

echo "$LOG_PREFIX published revisions.json"
