#!/usr/bin/env bash
# master_supervisor.sh — keep the Cartha Open Bible pipeline running at full
# capacity until every queued job is done, without human intervention.
#
# What it supervises:
#   * chapter translation workers (one supervise_worker.sh per logical worker
#     id, weighted per phase by backlog — spawns any that are missing)
#   * summary prewarm partitions for NT (already cached; starts one pass if
#     any cache entries are missing for the known NT corpus)
#   * OT-book summary prewarm (auto-kicks when a book's last chapter YAML is
#     committed to main — one partition per newly-complete OT book)
#   * stale claim release (any 'running' claim whose worker is dead for
#     >STALE_MINUTES gets returned to 'pending')
#
# Stop the supervisor with:  touch /tmp/cob-stop-supervisor
# (the loop checks every tick)
#
# Run once, run forever. Idempotent with respect to already-running workers.

set -u

COORD="${COORD:-/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha-translation}"
MASTER_LOG=/tmp/cob-master-supervisor.log
STOP_FILE=/tmp/cob-stop-supervisor
TICK_SECONDS="${TICK_SECONDS:-60}"
STALE_MINUTES="${STALE_MINUTES:-10}"

log() { echo "[$(date -u +%FT%TZ)] $*" >> "$MASTER_LOG"; }

# Target workers per phase, keyed by phase → "worker_id:worktree" list.
# Worktrees must already exist (pre-created git worktrees under /private/tmp).
# We use the existing ones from the project.
declare -a TARGETS=(
  "phase4-r1 phase4 /private/tmp/cartha-translation-phase2-e"
  "phase4-r2 phase4 /private/tmp/cartha-translation-phase2-f"
  "phase4-r3 phase4 /private/tmp/cartha-translation-phase2-h"
  "phase4-r4 phase4 /private/tmp/cartha-translation-phase2-i"
  "phase4-r5 phase4 /private/tmp/cartha-translation-phase2-act20"
  "phase5-a  phase5 /private/tmp/cartha-translation-phase3-a"
  "phase5-b  phase5 /private/tmp/cartha-translation-phase3-b"
  "phase5-c  phase5 /private/tmp/cartha-translation-phase2-g"
  "phase6-a  phase6 /private/tmp/cartha-translation-phase3-c"
  "phase6-b  phase6 /private/tmp/cartha-translation-phase3-d"
  "phase6-c  phase6 /private/tmp/cartha-translation-phase3-g"
  "phase6-d  phase6 /private/tmp/cartha-translation-phase3-h"
  "phase6-e  phase6 /private/tmp/cartha-translation-phase2-a"
  "phase6-f  phase6 /private/tmp/cartha-translation-phase2-b"
  "phase7-a  phase7 /private/tmp/cartha-translation-phase3-e"
  "phase7-b  phase7 /private/tmp/cartha-translation-phase3-f"
  "phase7-c  phase7 /private/tmp/cartha-translation-phase2-c"
  "phase7-d  phase7 /private/tmp/cartha-translation-phase2-d"
)

fetch_azure_key() {
  if [[ -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
    AZURE_OPENAI_API_KEY=$(aws secretsmanager get-secret-value \
      --secret-id cartha-azure-openai-key --region us-west-2 \
      --query SecretString --output text \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['api_key'])")
    export AZURE_OPENAI_API_KEY
    export AZURE_OPENAI_KEY="$AZURE_OPENAI_API_KEY"
    export AZURE_OPENAI_ENDPOINT="https://eastus2.api.cognitive.microsoft.com"
    export AZURE_OPENAI_DEPLOYMENT_ID="gpt-5-4-deployment"
    export BIBLE_SUMMARY_AZURE_DEPLOYMENT_ID="gpt-5-4-summary-deployment"
    export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
  fi
}

# Ensure each chapter-worker supervisor is running — only for phases that
# still have pending work. Drained phases are left alone.
ensure_chapter_workers() {
  # Which phases still have pending or running work?
  local phases_with_work
  phases_with_work=$(COORD="$COORD" python3 - <<'PY'
import os, sys, pathlib
sys.path.insert(0, os.path.join(os.environ["COORD"], "tools"))
import chapter_queue
db = chapter_queue.db_path_from(pathlib.Path(os.environ["COORD"]))
with chapter_queue.connect(db) as c:
    rows = [r["phase"] for r in c.execute("SELECT DISTINCT phase FROM jobs WHERE status='pending' OR status='running'")]
print(" ".join(rows))
PY
  )
  for entry in "${TARGETS[@]}"; do
    # shellcheck disable=SC2086
    read -r wid phase wt <<< "$entry"
    # Phase drained? skip.
    if [[ " $phases_with_work " != *" $phase "* ]]; then
      continue
    fi
    # Worktree missing? skip with warning.
    if [[ ! -d "$wt" ]]; then
      log "  skip $wid — worktree missing: $wt"
      continue
    fi
    # Already alive?
    if pgrep -f "supervise_worker.sh $wid " >/dev/null 2>&1; then
      continue
    fi
    nohup "$COORD/scripts/supervise_worker.sh" "$wid" "$phase" "$wt" \
      >/dev/null 2>&1 &
    disown
    log "  spawned chapter worker $wid (phase=$phase)"
  done
}

# Release any 'running' claim whose worker_id has no live supervisor AND
# was claimed more than $STALE_MINUTES minutes ago. This catches workers
# that were SIGKILLed, the machine slept, etc.
release_stale_claims() {
  COORD="$COORD" STALE_MINUTES="$STALE_MINUTES" python3 - <<'PY' >> "$MASTER_LOG" 2>&1
import os, sys, pathlib, subprocess, re, datetime as dt
sys.path.insert(0, os.path.join(os.environ["COORD"], "tools"))
import chapter_queue
stale_minutes = int(os.environ["STALE_MINUTES"])
db = chapter_queue.db_path_from(pathlib.Path(os.environ["COORD"]))

# Which worker ids have a live supervisor right now?
live = set()
try:
    out = subprocess.check_output(["pgrep", "-af", "supervise_worker.sh"], text=True)
    for line in out.splitlines():
        m = re.search(r"supervise_worker\.sh\s+(\S+)", line)
        if m: live.add(m.group(1))
except subprocess.CalledProcessError:
    pass

now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(minutes=stale_minutes)
cutoff_s = cutoff.replace(microsecond=0).isoformat().replace("+00:00","Z")
now_s = now.replace(microsecond=0).isoformat().replace("+00:00","Z")

with chapter_queue.connect(db) as c:
    rows = list(c.execute(
        "SELECT id, worker_id, phase, book_code, chapter, claimed_at "
        "FROM jobs WHERE status='running' AND claimed_at < ?",
        [cutoff_s],
    ))
    to_release = [r for r in rows if r["worker_id"] not in live]
    for r in to_release:
        c.execute(
            "UPDATE jobs SET status='pending', worker_id=NULL, claimed_at=NULL, "
            "updated_at=? WHERE id=?",
            [now_s, r["id"]],
        )
    # Also release any 'failed' claims so supervised workers get a chance
    # to retry them on the next cycle.
    fr = list(c.execute("SELECT id FROM jobs WHERE status='failed'"))
    for r in fr:
        c.execute(
            "UPDATE jobs SET status='pending', worker_id=NULL, claimed_at=NULL, "
            "last_error=NULL, updated_at=? WHERE id=?",
            [now_s, r["id"]],
        )
    c.commit()
    if to_release or fr:
        print(f"  released {len(to_release)} stale + {len(fr)} failed → pending")
PY
}

# Queue fully done? (nothing pending, nothing running)
queue_is_done() {
  COORD="$COORD" python3 - <<'PY'
import os, sys, pathlib
sys.path.insert(0, os.path.join(os.environ["COORD"], "tools"))
import chapter_queue
db = chapter_queue.db_path_from(pathlib.Path(os.environ["COORD"]))
with chapter_queue.connect(db) as c:
    n = c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending','running','failed')").fetchone()[0]
print(n)
PY
}

log "master supervisor starting  tick=${TICK_SECONDS}s  stale_cutoff=${STALE_MINUTES}m"
fetch_azure_key
rm -f "$STOP_FILE"

while :; do
  if [[ -f "$STOP_FILE" ]]; then
    log "stop file detected — exiting"
    exit 0
  fi

  remaining=$(queue_is_done 2>/dev/null || echo "?")
  sup_n=$(pgrep -f supervise_worker.sh 2>/dev/null | wc -l | tr -d ' ')
  wrk_n=$(pgrep -f chapter_worker.py 2>/dev/null | wc -l | tr -d ' ')
  log "tick  remaining=${remaining}  supervisors_alive=${sup_n}  chapter_workers_alive=${wrk_n}"

  if [[ "$remaining" == "0" ]]; then
    log "🎉 all chapter-translation jobs done. master supervisor exiting."
    exit 0
  fi

  release_stale_claims
  ensure_chapter_workers

  sleep "$TICK_SECONDS"
done
