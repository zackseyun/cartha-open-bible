# Methodology

The Cartha Open Bible follows a four-stage pipeline for every verse. Each
stage produces documented artifacts that are committed to this repository,
making the entire process auditable after the fact.

## Pipeline overview

```
  source text  ──▶  AI draft  ──▶  cross-check  ──▶  publication
  (SBLGNT,         (primary     (compare across     (commit +
   WLC, UHB,        LLM +        Claude + GPT +      tagged
   Rahlfs LXX)      prompt)      Gemini)             release)
```

Each stage is described below.

## Stage 1 — Source text preparation

Source texts are vendored under `sources/` with their original licenses and
verifiable provenance:

- **SBLGNT** (CC-BY 4.0) — Michael W. Holmes, ed., *The Greek New Testament:
  SBL Edition*. Society of Biblical Literature, 2010.
- **Westminster Leningrad Codex** — transcription of the Leningrad Codex
  (1008 AD).
- **unfoldingWord Hebrew Bible** (CC-BY-SA 4.0) — morphologically tagged
  Hebrew OT.
- **Rahlfs Septuagint** (public domain) — Alfred Rahlfs, ed., 1935.

Each verse references its source by stable identifier (book, chapter, verse)
and records any consulted variant apparatus.

## Stage 2 — AI draft

A primary LLM produces the draft using a prompt anchored in
`DOCTRINE.md`. The draft includes:

- English rendering
- Lexical decisions (key words, chosen glosses, alternatives, lexicon entry)
- Theological decisions (contested readings, alternatives preserved)
- Source-text citations

Draft metadata records:
- `model_id` — e.g., `gpt-5.4`, `claude-opus-4-7`
- `model_version` — knowledge cutoff + release tag
- `prompt_id` — versioned prompt identifier (e.g., `nt_draft_v1`)
- `prompt_sha256` — hash of the exact prompt used
- `temperature` — generation parameter
- `timestamp` — ISO 8601 UTC
- `output_hash` — sha256 of the model's raw output

The drafting script is `tools/draft.py`. Reproducibility is enforced: given
the same model, prompt hash, and source text, re-running the script should
produce the same draft (within model non-determinism bounds, which are
documented per draft).

## Stage 3 — Cross-check

Every verse is designed to be independently drafted by three frontier LLMs
running in parallel:

- Claude Opus (Anthropic)
- GPT (OpenAI)
- Gemini (Google)

Agreement is scored by normalized edit distance on the English rendering
and by overlap of lexical decisions. Thresholds:

- **≥ 0.90 agreement**: the draft proceeds with divergences noted as
  alternatives.
- **0.75–0.90 agreement**: divergences are surfaced as footnotes and
  documented in the verse YAML.
- **< 0.75 agreement**: the disagreement is escalated into a public
  GitHub issue for community discussion.

The cross-check script is `tools/cross_check.py`.

This stage is the single strongest defense against hallucination: three
independently-trained frontier models producing the same rendering is
strong evidence the rendering is not fabricated. Disagreements are not a
bug — they are the exact signal we want to surface.

## Stage 4 — Publication

Drafted and cross-checked verses are committed to the main branch. Each
commit message references the related source range and the model that
produced the draft. Tagged releases (`v0.1-preview`, `v0.2-pauline`, etc.)
correspond to phase completions.

Every verse in the repository is marked `status: draft`. The Cartha Open
Bible does not currently have a formal scholarly review process; published
drafts are the AI's output, with the full rationale visible alongside
each rendering.

## Reproducibility verification

`tools/verify.py <verse_id>` takes a published verse and re-runs the
LLM pipeline using the documented inputs. It reports:

- Whether the AI draft reproduces (modulo model non-determinism)
- Whether the cross-check agreement reproduces

Any third party can run this verification with no access to Cartha
infrastructure — only the public repository and the named LLM APIs.

## Consistency linting

`tools/consistency_lint.py` runs across the entire translation and flags:

- Same Greek / Hebrew word translated with different English glosses
  without a documented rationale
- Lexical decisions that contradict `DOCTRINE.md`'s default renderings
  without explicit override
- Missing source-text citations
- Empty or malformed verse records

Lint failures block merge to main.

## Public disagreement workflow

Any reader — scholar, pastor, or lay — can file an issue against a
specific verse using templates in `.github/ISSUE_TEMPLATE/`:

- `verse_concern.md` — general concern about a rendering
- `lexical_disagreement.md` — disagreement with a specific word choice
- `theological_disagreement.md` — disagreement with a contested-reading
  resolution

The project commits to responding publicly to every substantive issue.
Resolution may result in:

- No change, with rationale posted (and linked from the verse YAML)
- A revised rendering, committed with full provenance update
- Elevation of an alternative to main text with the original preserved
  in footnote (or vice versa)

All outcomes are documented publicly. Nothing happens in private email.
