# POB Revision Pass Roadmap

## What We've Done (Revision Pass 1 — April 2026)

- **Azure GPT-5.4**: ~41,000 verses revised (bulk pass, concurrency 15–20)
- **Gemini 3.1 Pro**: 97 Azure content-filtered verses (violent/sensitive OT passages)
- **Context provided**: raw source text + current draft
- **Context NOT provided**: lexical decisions, footnotes, prior revision history, book-level philosophy

### Known Limitations of Pass 1

1. **No lexical context** — model didn't know POB had chosen "slave" over "servant" for δοῦλος, or "Messiah" over "Christ" for Χριστός. This caused 496 regressions that required manual correction.
2. **No footnote awareness** — contested readings and translator notes not visible; model occasionally "resolved" footnoted ambiguity in one direction.
3. **No revision history** — model couldn't see that a human or prior model had already adjudicated a term.
4. **No book-level philosophy** — no awareness of book-specific translation conventions (e.g., T12P Greek vs. Aramaic backing, LXX vs. MT divergences).
5. **Azure content filter** — ~97 violent/graphic verses were blocked and had to fall back to Gemini, which lacked the same forced-tool-call schema.

### Infrastructure Built

- `tools/revision_policy.md` — loaded into all future revision system prompts
- `tools/known_regressions.yaml` — machine-readable regression case library
- `tools/check_regressions.py` — pre-commit regression guard (3 rules)
- `.git/hooks/pre-commit` — enforces regression check on every commit
- `azure_bulk_revise.py` + `gemini_bulk_revise.py` — both now include lexical decisions, footnotes, and most recent revision history in user message context

---

## Revision Pass 2 — Future Work

### What's Changed Since Pass 1

Both revision scripts (`azure_bulk_revise.py`, `gemini_bulk_revise.py`) now pass:
- **ESTABLISHED LEXICAL DECISIONS** (up to 6, with source word → chosen rendering + rationale + alternatives)
- **TRANSLATION FOOTNOTES** (up to 4, with marker and text)
- **MOST RECENT REVISION** (adjudicator, from→to, rationale)
- **revision_policy.md** injected into system prompt

This means the next bulk pass will be substantially more faithful to POB's own reasoning.

### Trigger Conditions

Run a second pass when any of the following occur:
- A new book is fully drafted (Gospel of Thomas, Jubilees — 465 stub files still undrafted)
- A model significantly better than GPT-5.4 or Gemini 3.1 Pro is available
- More than ~500 lexical decisions have been added or updated across the corpus
- A new `revision_policy.md` rule is added based on a newly identified regression pattern

### What Would Further Improve Pass 2

1. **Book-level context file** (`book_context.md` per book): translation philosophy, known LXX/MT divergences, character name conventions, recurring theological terms specific to that book. Feed into system prompt as `BOOK CONTEXT:` block.
2. **All lexical decisions** (not capped at 6): for heavily annotated verses (some have 15+), cap may drop important decisions. Consider dynamic cap based on token budget.
3. **Theological decisions block**: `theological_decisions` YAML key exists but not yet fed into revision context.
4. **Bidirectional cross-verse consistency**: model currently sees one verse at a time. Key terms (divine names, messianic titles, covenant terms) should be consistent across a whole chapter or book. Requires either a chapter-level pass or a post-pass consistency sweep.
5. **Human adjudication queue**: verses where the model flags `unchanged: false` with a high-confidence change should be surfaced for human review before final commit, rather than committed automatically.

### Undrafted Books (Not Revision Candidates)

465 stub files need full source + translation drafting before any revision pass:
- `translation/extra_canonical/gospel_of_thomas/` (305 files — placeholder stubs only)
- `translation/extra_canonical/jubilees/` (160 files)

These have only `['id', 'reference', 'unit', 'book']` keys. Use the OCR + draft pipeline (Gemini 3.1 Pro primary per POB OCR policy) before running revision.

### Cost Estimate (Pass 2, All Books)

| Model | Verses | Est. tokens/verse | Total tokens | Est. cost |
|---|---|---|---|---|
| Azure GPT-5.4 | ~41,000 | ~1,200 in + 300 out | ~62M | ~$300–400 |
| Gemini 3.1 Pro | ~500 (filtered) | ~1,200 in + 300 out | ~750K | ~$3–5 |

*Token estimate assumes average verse with 3–4 lexical decisions and 1 footnote adds ~300 tokens to context. Actual cost depends on model pricing at time of run.*

### Regression Guard (Always On)

Before every commit, `check_regressions.py` enforces:
1. No "Christ" (word boundary) in NT translation text → must be "Messiah"
2. No "servant" where source YAML has δοῦλ or עֶבֶד → must be "slave"
3. No truncation: current text < 35% of prior revision's `from` text (excludes verse 000 superscriptions)

Add new rules to `tools/known_regressions.yaml` and corresponding Python logic in `check_regressions.py` as new cases are identified.
