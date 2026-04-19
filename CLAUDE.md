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
[translation status page](https://cartha.com/cartha-open-bible/status).
It's committed like any other file — there is no server, no cron. The
cartha.website frontend fetches it directly from GitHub's raw CDN.

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
