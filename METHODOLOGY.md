# Methodology

The People's Open Bible is produced by a pipeline that treats every verse
as auditable. Each rendering is committed alongside the source text
behind it, the draft/revision metadata that shaped it, and any later
edit with its rationale. This document is a reproducibility map: it
shows the sources, review layers, and public artifacts someone would
need in order to inspect or reproduce the results without replaying
our internal work log step by step.

## Pipeline overview

```
  source text  ──▶  first draft  ──▶  revision pass    ──▶  spot fix         ──▶  publication
  (SBLGNT,         (GPT-5.4,          (Gemini 3.1 Pro       (Claude Opus 4.7      (commit +
   WLC, UHB,        prompt             reads draft           on individual         tagged
   Swete LXX,       anchored           against source;       verses needing        release +
   Charles APOT,    in DOCTRINE)       applies edits         targeted rework)      CDN publish)
   Bensly Latin,                       or marks
   Charles 1895                        unchanged)
   Ge'ez,
   Coptic NHC)
```

Model diversity is a deliberate quality layer: any revision pass run
by a different model from the first drafter helps fight same-model
bias. Cross-pollinating model families gives the strongest reasoning
and best outcome; spot fixes are an additional targeted pass when a
verse needs more scrutiny.

Per-verse stages 1–4 are described below. For revision policy and what
triggers a post-publication change, see
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md). For doctrinal and
lexical defaults, see [DOCTRINE.md](DOCTRINE.md) and
[PHILOSOPHY.md](PHILOSOPHY.md). For the source-licensing inventory,
see [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md).

## Reproducible workflow at a glance

The translation came together across four overlapping corpora. The
details below are not meant as a run-by-run history; they name the
source families, repeatable checks, and durable outputs that matter
for reproducing or auditing the work.

### Chapter 1 — Canonical corpus

| Reproducible step | Scope | What to inspect or repeat |
|---|---|---|
| Source selection | New Testament + Hebrew Bible | Use the canonical source bundles named in Stage 1: SBLGNT for the Greek New Testament, WLC/UHB for the Hebrew Bible, and the project-level source/licensing inventory in [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md). |
| Draft generation | Every canonical verse | Re-run the same per-verse draft pattern: source text + doctrine/philosophy anchors + versioned prompt/model metadata. The output is stored as verse YAML, not as an opaque compiled file. |
| Review and revision | Same canonical corpus | Run the source-facing review pass and inspect each verse's `revisions` block to see whether the reviewer changed the draft, accepted it unchanged, or preserved an alternate reading. |

The internal pilot and milestone order are preserved in commit history
and older operational docs, but they are not the important thing to
reproduce. For a reader or outside reviewer, the repeatable unit is
the verse record: source evidence, draft metadata, review result, and
published artifact.

### Chapter 2 — Deuterocanon

The deuterocanon broke the canonical pipeline because no
openly-licensed scan-grounded source corpus existed. Source
preparation became its own project before drafting could even start.

| Stage | Corpus | What it solved |
|---|---|---|
| Source rescue | Deuterocanonical OT (Swete LXX 12 books, 6,337 verses) | Source-text rescue, not drafting. Established the scan-grounded adjudication loop ([docs/PHASE8_CORPUS_QUALITY_RESCUE.md](docs/PHASE8_CORPUS_QUALITY_RESCUE.md)). Ended with 98.9% high-confidence verses (3,425/3,464 adjudicated). |
| Drafting | Apocrypha drafting — all 18 deuterocanonical books, 6,047 verses, plus Psalms of Solomon and Prayer of Manasseh | Drafting after the source rescue. Introduced the Gemini-reviewer pass for author-intent corrections (216 auto-applied; 451 Azure tier-3 adjudications). Prayer of Manasseh is a diplomatic reconstruction of Codex Alexandrinus from Charles 1913 APOT vol 1 pp. 636–640. |

### Chapter 3 — Extra-canonical witnesses

Extra-canonical material is translated for transparency about the
Jewish/early-Christian textual world — not claimed as scripture, but
surfaced so readers can see what existed alongside the canonical
books. Each language family forced a different OCR + parser stack.

| Corpus | Status |
|---|---|
| 2 Esdras — Latin Bensly 1895 + 6 daughter witnesses (Syriac, Ethiopic, Arabic, Armenian, Georgian) | Drafted. Established the multi-witness pipeline pattern for non-Greek primary sources. |
| Psalms of Solomon (Swete vol 3, 18 chapters, 330 verses) | Drafted. Proved the Swete pipeline extends to extra-canonical Greek. |
| Greek Apostolic Fathers — Didache, 1 Clement, Shepherd of Hermas | Drafted. Established the shared Greek extra-canonical pipeline. |
| 1 Enoch — Charles 1906 (critical, 23 MSS) + Dillmann 1851 | Drafted end-to-end in Ge'ez → English at corpus scale. |
| Jubilees — Charles 1895 (critical, 4 MSS) | Drafted end-to-end in Ge'ez → English at corpus scale. Output under `translation/extra_canonical/jubilees/`. |
| Testaments of the Twelve Patriarchs (Greek, Sinker 1879) | Drafted across all 12 testaments. Greek normalization complete. |
| Nag Hammadi (Coptic) — Gospel of Thomas, Gospel of Truth, Thunder Perfect Mind | OCR via Gemini 3.1 Pro (Coptic-aware). Gospel of Thomas redrafted using cross-family Coptic comparison (38/38 sayings). |

A note on the Ge'ez story, because it is the OCR finding most often
cited from this project: an earlier version of this document said
"Gemini 2.5 Pro in plaintext mode (not JSON) succeeds." That was true
in March 2026 and is documented in the commit history. It was
superseded on 2026-04-22 by a three-engine bake-off which found
Gemini 3.1 Pro at 80% page accuracy versus Azure GPT-5.4 at 46% on
Charles 1906 Ge'ez. Gemini 3.1 Pro is now the primary OCR engine for
all POB OCR (Ge'ez, Coptic, and Greek where Cambridge typography is
not the easier choice). Azure GPT-5.4 remains a useful second-pass
adjudicator.

### Chapter 4 — Standing review pipeline

| Layer | What it does |
|---|---|
| Stacked-review pass | Each verse gets a per-book author-intent context pass with **Gemini 3.1 Pro** (run on Vertex AI on the credit-funded `cartha-bible-vertex` project). Corrections auto-apply where evidence is strong; weaker findings escalate to a manually-adjudicated tier. The full negotiation history (`from`, `to`, rationale, reviewer model) is persisted in the verse YAML's `revisions` array. |
| Flywheel | A revisions flywheel runs every 30 minutes, regenerating `revisions.json` and pushing if any counts changed. As of the most recent snapshot, ~22,000 applied edits across ~18,700 verses, with ~60,000 review-pass verdicts logged across ~41,000 verses (including "agree" verdicts where no edit was applied). |

The standing review pipeline is the project's current center of
gravity. If you load a verse YAML at random today, the most likely
thing you'll see beyond the original draft is a revision block from
this pass.

## Stage 1 — Source text preparation

Source texts are vendored under `sources/` with their original
licenses and verifiable provenance. The headline sources:

- **SBLGNT** (CC-BY 4.0) — Michael W. Holmes, ed., *The Greek New
  Testament: SBL Edition*. Society of Biblical Literature, 2010.
- **Westminster Leningrad Codex** — transcription of the Leningrad
  Codex (1008 AD).
- **unfoldingWord Hebrew Bible** (CC-BY-SA 4.0) — morphologically
  tagged Hebrew OT.
- **Swete LXX** (public domain) — Henry Barclay Swete, ed., *The
  Old Testament in Greek According to the Septuagint*, 3 vols.
  (Cambridge University Press, 1909–1930). Vendored as our own OCR
  transcription under CC-BY 4.0 at `sources/lxx/swete/`.

For the deuterocanon and extra-canonical works, source preparation
is a substantial project of its own — the per-book table below.

### Stage 1A — Per-book source strategy

Different corpora demand different OCR engines and different witness
strategies. The choice is empirical, not aesthetic. The current
defaults reflect the 2026-04-22 OCR bake-off; earlier choices are
preserved in the phase docs for historical completeness.

| Corpus | Primary edition | OCR engine (current) | Why |
|---|---|---|---|
| LXX deuterocanon (12 books) | Swete 1909, vols 1–3 | Azure GPT-5.4 vision | Strong polytonic Greek; clean output on Cambridge typography |
| Prayer of Manasseh | Charles 1913 APOT vol 1 pp. 636–640 | Gemini 3.1 Pro | Apparatus-and-footnote reconstruction; needed structured semantic understanding |
| Psalm 151 | Swete vol 2 p. 432 | Azure GPT-5.4 | Standard Swete path |
| 2 Esdras | Bensly 1895 (critical Latin) + Violet 1910 (6 daughter witnesses in parallel columns) | Azure GPT-5.4 vision | Columnar Latin + parallel witness placement |
| 1 Enoch | Charles 1906 (critical, 23 MSS) + Dillmann 1851 | Gemini 3.1 Pro | Selected by 2026-04-22 OCR bake-off (3.1 Pro 80% vs Azure 46%); replaced earlier "Gemini 2.5 Pro plaintext" pipeline |
| Jubilees | Charles 1895 (critical, 4 MSS) | Gemini 3.1 Pro | Same Ge'ez constraint as 1 Enoch |
| Didache | Hitchcock & Brown 1884 | Azure GPT-5.4 + Gemini 3.1 Pro reviewer | Polytonic Greek; Gemini spot-checks Azure's drafts |
| 1 Clement | Funk 1901 (critical with notes) | Azure GPT-5.4 | Polytonic + interleaved Latin handled cleanly |
| Shepherd of Hermas | Lightfoot 1891 | Gemini 3.1 Pro (with Vertex fallback) | Page layout defeated Azure; Gemini Pro succeeds |
| Testaments of the Twelve Patriarchs | Sinker 1879 | Azure GPT-5.4 | Polytonic Greek; layout straightforward |
| Nag Hammadi (Thomas, Truth, Thunder) | NHC II,2 / NHC I,3 / NHC VI,2 facsimiles + Mattison/Zinner ecosystem | Gemini 3.1 Pro (Coptic-aware) | Coptic script; no Azure baseline |

Default, in one sentence: **Gemini 3.1 Pro for non-Greek and difficult
layouts; Azure GPT-5.4 for clean Cambridge polytonic Greek; the other
serves as second-pass reviewer.**

### Stage 1B — Three-tier scan-grounded adjudication

Every deuterocanonical verse is adjudicated against multiple
witnesses at full scan resolution before it is allowed to feed the
drafter:

1. **Tier 1 (4-source comparison at ≥3,000 px).** Our Swete
   transcription is compared against three independent witnesses:
   First1KGreek TEI, the Rahlfs-Hanhart digital edition (consulted as
   reference, see Zone-2 policy below), and Amicarelli/BibleBento.
   The verdict is **scan-grounded**: confidence is rated by visual
   legibility of the Cambridge page, not by witness agreement alone.
2. **Tier 2 (Gemini cross-check).** Verses that remain uncertain
   after Tier 1 are escalated to Gemini for a second opinion against
   the scan.
3. **Tier 3 (content-based page re-identification).** When running-
   head parsing has missed a page, the verse text itself is used to
   relocate the correct printed page and the rescue runs against the
   right scan.

The confidence rubric:

- **high** — printed form unambiguous; witnesses agree or disagree
  for explainable reasons; we trust this verse.
- **medium** — character-level ambiguity remains (ligature, breathing
  mark, faded ink); honest residual uncertainty.
- **low** — unverifiable from the available scans; deferred or held
  out of the drafter input.

The deuterocanon source rescue ended with 98.9% high (3,425/3,464
adjudicated), 1.1% medium, 0% low. The full rescue methodology —
including the failure taxonomy (wrong-page targeting, verse-number
drift, edition-specific numbering, true paleographic ambiguity) —
is documented in
[docs/PHASE8_CORPUS_QUALITY_RESCUE.md](docs/PHASE8_CORPUS_QUALITY_RESCUE.md).

The tooling: `tools/adjudicate_corpus.py`,
`tools/adjudicate_escalated.py`,
`tools/adjudicate_escalated_gemini.py`,
`tools/rescue_manual_pages.py`.

## Stage 2 — First draft

A primary LLM produces the draft using a prompt anchored in
[DOCTRINE.md](DOCTRINE.md). The draft includes:

- English rendering
- Lexical decisions (key words, chosen glosses, alternatives,
  lexicon entry consulted)
- Theological decisions (contested readings, alternatives preserved
  in footnotes)
- Source-text citations (edition + pages, archive.org-linkable
  where possible)

The drafter prompt loads, in addition to the verse, the relevant
doctrinal-anchor excerpt from DOCTRINE.md, the relevant philosophy
excerpt from [PHILOSOPHY.md](PHILOSOPHY.md), and any per-book
apparatus or witness parallels recorded for that book.

Draft metadata recorded per verse:

- `model_id` — e.g., `gpt-5.4`, `gemini-3.1-pro-preview`,
  `claude-opus-4-7` (used for occasional spot fixes)
- `model_version` — knowledge cutoff + release tag
- `prompt_id` — versioned prompt identifier (e.g., `nt_draft_v1`)
- `prompt_sha256` — hash of the exact prompt used
- `temperature` — generation parameter
- `timestamp` — ISO 8601 UTC
- `output_hash` — sha256 of the model's raw output

The drafting script is `tools/draft.py`. Reproducibility is
enforced: given the same model, prompt hash, and source text,
re-running the script produces the same draft within model
non-determinism bounds, which are documented per draft.

## Stage 3 — Revision pass

What actually runs on every verse today is a **two-stage pipeline**:
a primary drafter, followed by an independent revision pass on a
different model family. The original design document called for
running three frontier models in parallel and scoring agreement on
edit distance and lexical-key overlap. We still use that comparison
selectively for high-uncertainty verses, but it is not the default
per-verse path. The honest description is:

1. **Primary drafter.** Most canonical books were drafted by GPT-5.4;
   Ge'ez and Coptic books were drafted with Gemini 3.1 Pro feeding
   off Gemini 3.1 Pro OCR transcripts; specific verses with content
   filtering issues were redrafted with Gemini 3.1 Pro as a fallback
   (97 Azure-blocked verses in 4 Maccabees and other martyrdom
   passages, processed 2026-04-23). Claude Opus 4.7 has been used
   for occasional spot fixes on individual verses needing targeted
   rework or another independent model-family pass.
2. **Revision pass.** Gemini 3.1 Pro running on Vertex AI
   reads each draft against the source text, identifies lexical
   disagreements, awkward English, and category-1 grammar issues,
   and adjudicates whether to apply a change or mark the verse
   `unchanged`. Every verdict is logged. Every applied edit is
   recorded in the verse YAML's `revisions` array with `from`, `to`,
   rationale, and `reviewer_model`.
3. **Tier-3 adjudicator.** Verses where the primary drafter and the
   revision pass disagree on something doctrinally salient are
   escalated to Azure GPT-5.4 for a third opinion. The deuterocanon
   drafting pass produced 451 such adjudications.
4. **Doctrine + grammar lint.** A regression layer catches cases
   where an automated revision silently violates a documented
   project policy (e.g., Χριστός being changed back to "Christ"
   against DOCTRINE.md). Reverts are visible in the same
   `revisions` array.

This is the project's strongest defense against hallucination. A
draft from one model family, read against the source by a different
model family, with a separate adjudicator on disagreements and a
mechanical lint on policy violations, produces a more trustworthy
verse than any single model run in isolation. Disagreements are not
a bug — they are the signal we want to surface.

For verses that the lint or adjudicator has flagged repeatedly, a
selective comparison-of-three-models run is invoked, scored on
edit-distance + lexical-key overlap. The scoring thresholds and
escalation rules live with the tooling rather than on this page;
see `tools/cross_check.py`. The revision-pass tooling lives in
`tools/gemini_bulk_revise.py` and
`tools/adjudicate_escalated_gemini.py`.

## Stage 4 — Publication

Drafted and revised verses are committed to the `main` branch.
Each commit message references the related source range and the
model that produced the draft. Earlier preview tags exist in the
git history as historical milestones; current state of the
translation is well beyond them.

Every verse in the repository is marked `status: draft`. The Cartha
Open Bible does not currently have a formal scholarly review
process; published drafts are the AI's output, with the full
rationale visible alongside each rendering. Revision happens after
publication, in the open, with full provenance preserved (see
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md)).

The website and mobile apps do **not** read this repo directly for
Bible text. They both pull a compiled JSON snapshot from the CDN at
`https://bible.cartha.com`, regenerated whenever new drafts or
revisions land on `main`.

### Per-verse provenance schema

Each verse YAML at `translation/<testament>/<book>/<chap>/<verse>.yaml`
records:

- `source.text` — the Greek/Hebrew/Ge'ez/Latin/Coptic string
- `source.edition` — named edition (e.g., `lxx-swete-1909`,
  `charles-1913-apot-vol1`, `charles-1895-ethiopic`)
- `source.pages` — archive.org-linkable page numbers
- `source.confidence` — high/medium/low (scan-grounded for
  deuterocanon)
- `adjudication` (if scan-grounded) — which witnesses agreed,
  which didn't, rescuer's verdict
- `translation.text` — the English rendering
- `lexical_decisions` — per-word gloss + rationale + alternatives
- `theological_decisions` — contested readings, alternatives,
  footnotes
- `ai_draft` — model_id, prompt_hash, output_hash, timestamp
- `revisions` — array of `{from, to, rationale, reviewer_model,
  timestamp}` entries; the original draft is preserved alongside
  every applied edit

Schema definition: `schema/verse.schema.json`.

A reader who wants to verify any verse can pull the Zone-1 source
edition from archive.org, find the cited pages, compare the printed
text against `source.text`, and inspect the `confidence` and
`adjudication` fields to see what was uncertain.

## Revision policy

Drafts are not the final word. Every phase is followed by a
revision pass that runs in three layers
([REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md),
[docs/REVISION_PROCESS.md](docs/REVISION_PROCESS.md)):

- **Layer 1 (during drafting).** `tools/consistency_lint.py` runs
  per commit, flagging same-lemma-different-gloss without rationale,
  contradictions of DOCTRINE.md defaults, missing source citations,
  and malformed YAML. Lint failures block merge to main.
- **Layer 2 (per-phase revision).** After a phase draft is complete,
  the corpus is revised in thematic batches. The Pauline runbook
  ([docs/PHASE1_REVISION_RUNBOOK.md](docs/PHASE1_REVISION_RUNBOOK.md))
  defines five batches: (1) Pauline core vocabulary (πίστις,
  δικαιοσύνη, σάρξ, νόμος, χάρις, κύριος, Χριστός), (2) Eucharistic
  and body-of-Christ passages, (3) OT citation handling, (4)
  readability sweep, (5) cross-reference verification.
- **Layer 3 (whole-Bible).** Once a full draft exists across both
  testaments, voice is unified across OT/NT and cross-phase
  inconsistencies are resolved.

What triggers a revision: real English grammar awkwardness;
rhetorical-force loss; wordplay the draft flattened; scholarly
preference drift without a textual reason; corpus-level
inconsistencies. What does **not** trigger a revision: stylistic
preference, theological re-interpretation absent textual evidence,
lexicon-entry quibbles. Full criteria in
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md).

Revision commits preserve the original `ai_draft` provenance — the
prior rendering is visible in git log, not deleted from the YAML.
Commit subjects start with `revise`, `polish`, `normalize`, `rename`,
or `consistency` so the public progress dashboard can filter them.

### Global normalizations

A small number of decisions apply at corpus scale, not per-verse.
These are documented in
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md) under
"Global-scope normalizations" and include:

- **Χριστός → Messiah** (decided 2026-04-18, applied to ~68 verses).
  "Christ" preserved as alternative in footnotes. **Liturgical
  carve-outs**: Pauline benediction formulas (Rom 16:20, 2 Cor
  13:13, Gal 6:18, Phil 4:23, 1 Thess 5:28, 2 Thess 3:18, Phlm 25,
  2 Cor 8:9) and the Phil 2:11 confession revert to "Christ"
  because they are fixed liturgical forms in the early church.
- **μετανοέω context-sensitive rendering** (decided 2026-04-19).
  "Change of mind" / "change your thinking" in cognitive contexts;
  "repent" in specific-sin contexts. Per-context rule.
- **יְהוָה → Yahweh** throughout the OT and deuterocanon, against
  the traditional "LORD". The divine name is a name. Where the NT
  quotes an OT YHWH passage using Greek Κύριος, the NT verse uses
  "Lord" to preserve the Greek surface — these are quotation
  markers, not theological softening.

Each normalization has a commit history showing the mechanical
change and a documented set of carve-outs.

## Reproducibility verification

`tools/verify.py <verse_id>` takes a published verse and re-runs the
LLM pipeline using the documented inputs. It reports:

- Whether the first draft reproduces (modulo model non-determinism)
- Whether the revision pass reproduces
- Whether the OCR for the cited source page reproduces (for
  scan-grounded verses)

Any third party can run this verification with no access to Cartha
infrastructure — only the public repository, the cited Zone-1
sources from archive.org, and the named LLM APIs.

## Consistency linting

`tools/consistency_lint.py` runs across the entire translation and
flags:

- Same Greek / Hebrew word translated with different English glosses
  without a documented rationale
- Lexical decisions that contradict `DOCTRINE.md`'s default
  renderings without explicit override
- Missing source-text citations
- Empty or malformed verse records
- YAML schema violations against `schema/verse.schema.json`

Lint failures block merge to main. The lint output is also
consumed by the revision Layer-2 batching — same-lemma-different-gloss
clusters become revision targets.

## Public disagreement workflow

Any reader — scholar, pastor, or lay — can file an issue against a
specific verse using templates in `.github/ISSUE_TEMPLATE/`:

- `verse_concern.md` — general concern about a rendering
- `lexical_disagreement.md` — disagreement with a specific word
  choice
- `theological_disagreement.md` — disagreement with a contested-
  reading resolution

The reader's "Suggest Revision" form on cartha.com prefills these
templates from the verse YAML so the issue is self-contained.

The project commits to responding publicly to every substantive
issue. Resolution may result in:

- No change, with rationale posted (and linked from the verse YAML)
- A revised rendering, committed with full provenance update
- Elevation of an alternative to main text with the original
  preserved in footnote (or vice versa)

All outcomes are documented publicly. Nothing happens in private
email.
