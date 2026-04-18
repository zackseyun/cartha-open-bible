# Phase 1 Revision Runbook — Pauline Epistles

This runbook assumes the **Phase 1 first pass is complete**, lint is clean, and the repo is ready for the first real Pauline revision cycle.

Current baseline:
- First-pass Pauline draft complete
- `v0.2-pauline` tagged
- `lint_reports/phase1-pauline.md` clean

## Goal

Improve Phase 1 from a complete AI draft into a more stable Pauline release candidate without losing provenance or creating unstructured drift.

This runbook should be executed **before Phase 2 drafting becomes the main focus**.

## Revision order

### Batch 1 — Pauline core doctrinal vocabulary
Focus terms:
- πίστις
- δικαιοσύνη
- σάρξ
- νόμος
- χάρις
- κύριος
- Χριστός / Messiah vs Christ carve-outs

Questions:
- Are the renderings internally coherent across Romans, Galatians, Corinthians, and Pastorals?
- Are we over-flattening distinct contexts?
- Are current carve-outs documented well enough?

Suggested commit styles:
- `revise: harmonize Pauline pistis renderings`
- `revise: tighten sarx and law terminology in Romans-Galatians`
- `revise: clarify Messiah/Christ carve-outs in Pauline benedictions`

### Batch 2 — Eucharistic / body / participation passages
Focus passages:
- 1 Corinthians 10
- 1 Corinthians 11
- Romans 12
- 1 Corinthians 12

Questions:
- Are σῶμα / κοινωνία / αἷμα / ἄρτος choices consistent?
- Are we preserving sacramental tension without forcing doctrinal resolution?
- Are footnotes sufficient where traditions diverge strongly?

Suggested commit styles:
- `revise: clarify Eucharistic participation language in 1 Corinthians 10-11`
- `revise: harmonize body imagery in Romans 12 and 1 Corinthians 12`

### Batch 3 — Citation and quotation handling
Focus areas:
- Romans 3-4
- Romans 9-11
- Galatians 3-4
- 2 Corinthians and Pastorals where explicit formulas occur

Questions:
- Are OT quotations translated transparently?
- Are we surfacing major alternatives with footnotes when needed?
- Are quotation formulas visibly consistent?

Suggested commit styles:
- `revise: harmonize OT citation handling in Romans and Galatians`
- `revise: tighten quotation wording in Romans 9-11`

### Batch 4 — Readability cleanup in dense chapters
Focus areas:
- Romans 3-8
- 1 Corinthians 13-15
- 2 Corinthians 3-6
- Ephesians 1-3

Questions:
- Where is the English technically accurate but clunky?
- Where are sentence breaks, cadence, or apposition making reading harder than necessary?
- Can readability improve without losing lexical transparency?

Suggested commit styles:
- `revise: smooth dense Pauline English in Romans 3-8`
- `revise: improve readability in 2 Corinthians 3-6`

### Batch 5 — Cross-reference pass
Use:
- `docs/CROSS_REFERENCE_PASS.md`
- `docs/REVISION_PROCESS.md`

Focus:
- OT citation echoes
- recurring Pauline formulas
- title usage and covenant terms
- allusions worth preserving in footnotes

Suggested commit styles:
- `revise: add Pauline cross-reference footnotes for Abraham citations`
- `revise: align repeated kingdom and promise language in Paul`

## Execution rules

- Work in **substantive batches**, not scattered verse edits.
- After each batch:
  1. rerun `consistency_lint.py` on Phase 1,
  2. confirm no net new unresolved flags,
  3. commit with a clear lexical/stylistic reason.
- Keep revisions on `main`.
- Preserve AI provenance fields.
- Do not change human-review state.

## Exit criteria for Pauline revision pass

Phase 1 revision pass is ready to close when:
- targeted revision batches above are complete,
- `lint_reports/phase1-pauline.md` remains clean,
- major Pauline terminology drift is resolved or explicitly deferred,
- cross-reference notes for major quotation/allusion clusters are added where helpful,
- `CHANGELOG.md` is updated with a short Phase 1 revision summary if needed.

## After this

Once the Pauline revision pass is stable:
1. keep the queue system ready on `main`,
2. begin Phase 2 drafting with chapter workers,
3. preserve the same rhythm: first-pass draft → lint → revision → cross-reference.
