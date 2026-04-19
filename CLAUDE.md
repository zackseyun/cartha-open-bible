# CLAUDE.md — Cartha Open Bible (working notes for agents)

Conventions for AI agents (or humans) working in this repo.

## Commit style

- **No `Co-Authored-By: Claude` trailer on any commit.** This repo's
  history is public-facing — keep it attributed cleanly to the human
  maintainers. Remove the trailer from any existing commit if it slips
  in.
- Commit subjects for revision-pass work start with one of these verbs
  so the public status dashboard can filter them: `revise`, `polish`,
  `normalize`, `rename`, `consistency`. Drafting commits don't use these
  prefixes.

## Regenerating `status.json`

`status.json` at the repo root is the snapshot that powers the public
[translation progress page](https://cartha.com/cartha-open-bible/progress).
It's committed like any other file — there is no server, no cron. The
cartha.website frontend fetches it directly from GitHub's raw CDN and
pins each coverage number to the `commit_sha` embedded in the file.

**When to regenerate:**

- After merging a batch of drafting work.
- After a revision pass or a normalization pass.
- Before any announcement that quotes progress numbers.

**How to regenerate:**

```bash
python3 tools/build_status.py
git add status.json
git commit -m "status: regenerate snapshot"
git push
```

The script walks `translation/` + runs `git log --` against the
`translation/` path. It does not parse YAML contents — all signals are
derived from directory structure and commit subjects, so a cold run is
well under a second.

**Pin caveat:** the `commit_sha` embedded in `status.json` is the HEAD
at generation time, which is one commit behind the commit that adds the
status.json itself. That's correct: the snapshot reflects the repo
state *as of* the pinned SHA, before the snapshot was committed.

**Schema:** see `tools/build_status.py` for the authoritative shape.
Bump `schema_version` when adding fields the frontend must branch on.

## Publishing to clients — CDN pipeline

The website and mobile apps do **not** read this repo directly for
Bible text. They both pull a compiled JSON snapshot from the CDN at
`https://bible.cartha.com`. The pipeline is:

```
main (committed drafts)
   ↓  (scripts/publish_cob.sh)
Lambda: cartha-cob-publisher
   ↓
bible.cartha.com/manifest.json   (tiny, revalidated on each read)
bible.cartha.com/cob_preview.json (large body, cache-busted by manifest.version)
   ↓                    ↓
website bibleData.js    mobile CobRuntimeSync
```

Clients compare their cached version sha to `manifest.version`; if
different, they fetch the new body. Nothing ships to clients until
the Lambda runs.

**To force-refresh what clients see from whatever is on `main` right
now:**

```bash
scripts/sync_cob.sh                 # cherry-pick any ready jobs + push + publish
scripts/sync_cob.sh --publish-only  # just re-publish whatever is already on main
scripts/sync_cob.sh --merge-only    # cherry-pick + push, skip publish
```

This is the one-shot manual equivalent of `scripts/supervise_merge.sh`.
Use it after a revision pass, after a direct commit to `main`, or any
time you suspect the CDN has drifted behind `main`.

**Autonomous alternative:** `scripts/master_supervisor.sh` keeps
translation workers, the merge supervisor, and OT summary prewarmers
all alive in a loop. It exits when the queue drains. Pause with
`touch /tmp/cob-stop-supervisor`; stop fully with `pkill -f
master_supervisor.sh`. There is deliberately no launchd plist — this
is a finite project and running as a daemon encourages forgetting to
stop it.

**Landmine that bit us on 2026-04-19 — don't reintroduce:** the
earlier version of `tools/chapter_merge.py` used
`git branch --contains <sha>` to decide whether a draft commit was
"already on main." That returns true if *any* branch — including the
`codex/*` per-worktree branches — contains the sha, so it silently
marked 357 uncherrypicked drafts as merged and the CDN stayed on 42
of 66 canonical books while the SQL claimed 100% completion. The
correct check, now in place, is
`git merge-base --is-ancestor <sha> HEAD`. If you change the merge
script, keep that check or an equivalent that pins to `main`
specifically.

## Public pages that depend on this repo

The cartha.website frontend reads three live endpoints from this
repo's `main` branch:

- `status.json` — the status dashboard.
- `translation/<testament>/<slug>/<NNN>/<VVV>.yaml` — per-verse
  provenance page at `/cartha-open-bible/verse?ref=<CODE>.<CH>.<V>`.
- The issue tracker at `github.com/zackseyun/cartha-open-bible/issues`
  — the Suggest Revision form in the reader opens a prefilled GitHub
  issue, so labels/policies defined there shape what users see.

Changing directory layout or file schema breaks those pages. If you
restructure, update the consuming code in the cartha.website repo
(`src/app/(main)/cartha-open-bible/`) in the same change set.

## Policy references

- Revision philosophy + criteria: [REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md)
- Drafting pipeline + cross-check: [METHODOLOGY.md](METHODOLOGY.md)
- Doctrinal/translation principles: [DOCTRINE.md](DOCTRINE.md) and
  [PHILOSOPHY.md](PHILOSOPHY.md)
