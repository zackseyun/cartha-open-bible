# Methodology

The Cartha Open Bible is produced by a pipeline that treats every verse
as auditable: each rendering is committed to this repository alongside
its source text, the OCR evidence behind that source text, the prompt
and model that drafted it, the cross-check signals that validated it,
and any subsequent revision with its rationale. This document describes
how that pipeline actually works in practice — including the parts
that are not pretty.

The per-verse pipeline is source text → AI draft → multi-model
cross-check → publication. Underneath it sits an OCR + adjudication
system that prepares deuterocanonical and extra-canonical sources
before they ever reach the drafter.

For revision policy and what triggers a post-publication change, see
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md). For doctrinal and
lexical defaults, see [DOCTRINE.md](DOCTRINE.md) and
[PHILOSOPHY.md](PHILOSOPHY.md). For the source-licensing inventory,
see [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md).

## Pipeline overview

```
  source text  ──▶  AI draft  ──▶  cross-check  ──▶  publication
  (SBLGNT,         (primary     (compare across     (commit +
   WLC, UHB,        LLM +        Claude + GPT +      tagged
   Swete LXX,      prompt)       Gemini, score       release +
   Charles APOT,                  by edit            CDN publish)
   Charles 1895                   distance + lex
   Ge'ez, Bensly                  overlap)
   Latin, etc.)
```

Per-verse stages 1–4 are described below.

## Phases

The translation has been built in numbered phases. Each phase targets
a specific corpus and a specific risk; phase docs in `docs/` record
the operational lessons of each.

| Phase | Corpus | What it solved |
|---|---|---|
| 0 | Philippians | Pilot. Proved the four-stage per-verse loop end-to-end on one short epistle. |
| 1 | Pauline epistles (Romans → Philemon, ~1,925 verses) | First full-scale draft + cross-check. The first revision runbook ([docs/PHASE1_REVISION_RUNBOOK.md](docs/PHASE1_REVISION_RUNBOOK.md)) was written here, and the global Χριστός → Messiah and μετανοέω rule decisions were made off the back of this corpus. |
| 8 | Deuterocanonical OT (Swete LXX 12 books, 6,337 verses) | Source text rescue, not drafting. Established the scan-grounded adjudication loop ([docs/PHASE8_CORPUS_QUALITY_RESCUE.md](docs/PHASE8_CORPUS_QUALITY_RESCUE.md)). Ended with 98.9% high-confidence verses (3,425/3,464 adjudicated). |
| 8b | 2 Esdras (Latin Bensly 1895 + 6 daughter witnesses: Syriac, Ethiopic, Arabic, Armenian, Georgian) | Multi-witness pipeline pattern for non-Greek primary sources. Drafting deferred until the witness parser stabilized. |
| 8c | 1 Enoch (Ge'ez, Charles 1906 + Dillmann 1851) | Established the Ge'ez OCR pipeline. Discovered that Azure GPT-5.4 fails outright on Ge'ez, Gemini 2.5 Flash hallucinates, and Gemini 2.5 Pro in **plaintext mode** (not JSON) succeeds. JSON escaping inflates 3-byte Ethiopic characters into 6 response tokens, blowing the 32K token budget on dense pages. |
| 8d | Jubilees (Ge'ez, Charles 1895) | Scaled the Ge'ez pipeline. Early Gemini Pro tests showed only ~44% run-to-run consistency until plaintext mode replaced JSON. |
| 8e | Psalms of Solomon (Swete vol 3 pp. 788–810, 18 chapters, 330 verses) | Proved the Swete pipeline extends to extra-canonical Greek. |
| 8f | Greek extra-canonical: Didache, 1 Clement, Shepherd of Hermas, Testaments of the Twelve Patriarchs | Established the shared Greek extra-canonical pipeline (Azure GPT-5.4 primary, Gemini reviewer). First-pass drafts of Didache (16 ch) and 1 Clement (65 ch). Released as preview tag v0.9. |
| 9 | Apocrypha drafting (all 17 deuterocanonical books, 6,047 verses) + Psalms of Solomon + Prayer of Manasseh | Drafting execution after Phase 8's source rescue. Introduced the Gemini-reviewer pass for author-intent corrections (216 auto-applied; 451 Azure tier-3 adjudications). Prayer of Manasseh is a diplomatic reconstruction of Codex Alexandrinus from Charles 1913 APOT vol 1 pp. 636–640. |
| 10 | Greek extra-canonical drafting + 2 Esdras Latin → multi-witness | Stacked-review pipeline: each verse gets a per-book author-intent context pass with Gemini 3.1 Pro; corrections auto-applied where evidence is strong. |
| 11 | 1 Enoch full chapter-level OCR (Charles 1906 + Dillmann 1851) | Verse extraction still pending; drafter wiring deferred. |
| 12c–12d | Jubilees end-to-end (Ge'ez Charles 1895 → verse-level English) | Ge'ez-to-English pipeline working end-to-end at corpus scale. Output committed under `translation/extra_canonical/jubilees/`. |
| 14 | Testaments of the Twelve Patriarchs (Greek, Sinker 1879) | Pilot per-testament drafting (Reuben, Simeon, Levi, Judah, Joseph, Issachar–Asher with Greek pilots); raw OCR coverage still poor; layout parser in progress. |

Phase numbers are not strictly sequential because corpora are
addressed in parallel — Phase 8 source rescue ran concurrently with
Phase 9 drafting on the same books once the source text was
high-confidence enough.

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
strategies. The choice is empirical, not aesthetic.

| Corpus | Primary edition | OCR engine | Why |
|---|---|---|---|
| LXX deuterocanon (12 books) | Swete 1909, vols 1–3 | Azure GPT-5.4 vision | Strong polytonic Greek; clean output on Cambridge typography |
| Prayer of Manasseh | Charles 1913 APOT vol 1 pp. 636–640 | Gemini 3.1 Pro text extraction | Apparatus-and-footnote reconstruction; needed structured semantic understanding |
| Psalm 151 | Swete vol 2 p. 432 | Azure GPT-5.4 | Standard Swete path |
| 2 Esdras | Bensly 1895 (critical Latin primary) + Violet 1910 (parallel columns of 6 daughter witnesses) | Azure GPT-5.4 vision | Columnar Latin + parallel witness placement |
| 1 Enoch | Charles 1906 (critical, 23 MSS) + Dillmann 1851 | **Gemini 2.5 Pro plaintext** (not JSON) | Azure fails on Ge'ez; Gemini 2.5 Flash hallucinates; Pro succeeds — but only in plaintext mode |
| Jubilees | Charles 1895 (critical, 4 MSS) | Gemini 2.5 Pro plaintext | Same Ge'ez constraint as 1 Enoch |
| Didache | Hitchcock & Brown 1884 | Azure GPT-5.4 + Gemini 2.5 Pro reviewer | Polytonic Greek; Gemini spot-checks Azure's drafts |
| 1 Clement | Funk 1901 (critical with notes) | Azure GPT-5.4 | Polytonic + interleaved Latin translation handled cleanly |
| Shepherd of Hermas | Lightfoot 1891 | Azure GPT-5.4 | Raw OCR captured; segmentation/parser still in progress |
| Testaments of the Twelve Patriarchs | Sinker 1879 | Azure GPT-5.4 | Pilot; layout understanding incomplete |

The most consequential discovery here was the Ge'ez plaintext finding.
Until 2026-04-21 the Ge'ez pipeline was effectively broken — 44%
run-to-run consistency on the same input page. The fix was not a
better prompt; it was abandoning the JSON response format. Each
3-byte Ethiopic character was being escaped into ~6 response tokens,
which exhausted the 32K token budget on dense pages and truncated
the output. Plaintext mode preserves ~1,200 tokens per page and
gives stable transcriptions.

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

Phase 8 ended with 98.9% high (3,425/3,464 adjudicated), 1.1%
medium, 0% low. The full rescue methodology — including the failure
taxonomy (wrong-page targeting, verse-number drift, edition-specific
numbering, true paleographic ambiguity) — is documented in
[docs/PHASE8_CORPUS_QUALITY_RESCUE.md](docs/PHASE8_CORPUS_QUALITY_RESCUE.md).

The tooling: `tools/adjudicate_corpus.py`,
`tools/adjudicate_escalated.py`,
`tools/adjudicate_escalated_gemini.py`,
`tools/rescue_manual_pages.py`.

## Stage 2 — AI draft

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

- `model_id` — e.g., `gpt-5.4`, `claude-opus-4-7`
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

## Stage 3 — Cross-check

Every verse is independently drafted by three frontier LLMs running
in parallel:

- Claude Opus (Anthropic)
- GPT (OpenAI)
- Gemini (Google)

The specific model versions are recorded per-draft in the YAML
`ai_draft.model_id` field; the current phase's versions are named
in [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md). This document stays
model-version-agnostic so the pipeline description does not churn
with each model release.

Agreement is scored on two axes:

- **Normalized Levenshtein edit distance** on the English rendering
  (after whitespace normalization, punctuation collapse, and
  case-folding). Runs ~1.0 for identical renderings, falls toward
  0 as the renderings diverge.
- **Lexical-key overlap** on the `lexical_decisions` keys (the
  Greek/Hebrew lemmata each model chose to gloss). Two models
  reaching the same English rendering for *different* glossed
  lemmata is weak agreement; two models reaching slightly different
  English rendering with the same glossed lemmata is strong
  agreement.

Thresholds:

- **≥ 0.90 agreement**: the draft proceeds with divergences noted
  as alternatives in the YAML.
- **0.75–0.90 agreement**: divergences are surfaced as footnotes
  and documented in the verse YAML.
- **< 0.75 agreement**: the disagreement is escalated into a
  public GitHub issue for community discussion.

The cross-check script is `tools/cross_check.py`.

This stage is the project's strongest defense against hallucination.
Three independently-trained frontier models producing the same
rendering is strong evidence the rendering is not fabricated.
Disagreements are not a bug — they are the signal we want to
surface.

## Stage 4 — Publication

Drafted and cross-checked verses are committed to the `main` branch.
Each commit message references the related source range and the
model that produced the draft. Tagged releases (`v0.1-preview`,
`v0.2-pauline`, `v0.9` for the Greek extra-canonical preview, etc.)
correspond to phase completions.

Every verse in the repository is marked `status: draft`. The Cartha
Open Bible does not currently have a formal scholarly review
process; published drafts are the AI's output, with the full
rationale visible alongside each rendering. Revision happens after
publication, in the open, with full provenance preserved (see
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md)).

### Per-verse provenance schema

Each verse YAML at `translation/<testament>/<book>/<chap>/<verse>.yaml`
records:

- `source.text` — the Greek/Hebrew/Ge'ez/Latin string
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
- `revision` (if applicable) — reviser, reason, prior rendering

Schema definition: `schema/verse.schema.json`.

A reader who wants to verify any verse can pull the Zone-1 source
edition from archive.org, find the cited pages, compare the printed
text against `source.text`, and inspect the `confidence` and
`adjudication` fields to see what was uncertain.

## Revision passes

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

- Whether the AI draft reproduces (modulo model non-determinism)
- Whether the cross-check agreement reproduces
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

