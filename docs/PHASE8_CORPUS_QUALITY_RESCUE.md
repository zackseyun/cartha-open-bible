# Phase 8 corpus quality rescue

This document explains how the Phase 8 deuterocanonical corpus was
improved *after* the first broad OCR + adjudication pass, and how to
repeat that work later without guessing.

The short version is simple:

1. start from the residual-uncertainty list,
2. inspect the exact verse in the exact scan page,
3. identify whether the problem is OCR, page targeting, or verse-number
   mapping,
4. run a **targeted rescue** on the real page,
5. only promote confidence if the printed form is actually legible.

That was the method used to eliminate the last Phase 8 `low` verses and
eventually to eliminate the last `medium` verses as well.

## Why this doc exists

The biggest lesson from the end of Phase 8 was that several “hard”
residuals were not truly paleographic dead ends. Some were still caused
by infrastructure issues:

- the rescue pass was looking at the wrong page,
- Swete’s alternate Sirach numbering had not been mapped correctly,
- a late-chapter verse block in 1 Esdras had drifted out of alignment,
- a small printed form had been treated as uncertain before someone
  checked the actual page image closely enough.

So the quality-improvement loop needed to be documented explicitly. We
do not want future sessions to rediscover the method from git history.

## The rescue workflow

### 1) Start from the residual list

Use:

- `sources/lxx/swete/RESIDUAL_UNCERTAINTY.md`
- `sources/lxx/swete/final_corpus_adjudicated/*.jsonl`
- `sources/lxx/swete/adjudications/*.json`

The first file tells you *which* verses remain medium/low. The JSONL and
adjudication files tell you *what reading is currently in the corpus* and
*why it got its confidence label*.

### 2) Verify the page before changing the text

Do not assume the `source_pages` list is right just because it exists.

Before changing anything, check:

- the local transcription page in `sources/lxx/swete/transcribed/`,
- and the actual scan image fetched through
  `tools/transcribe_source.py::fetch_swete_image`.

This is the key habit that unlocked the final improvements. Several
residuals turned out to be “wrong page attached” problems rather than
“scan impossible to read” problems.

### 3) Classify the failure mode

In practice, the residuals fell into four buckets:

1. **Wrong page targeting**
   - the adjudicator was honest, but it had not been given the page that
     contained the verse.
2. **Verse-number drift**
   - the page was right, but our chapter/verse mapping had slipped.
3. **Edition-specific numbering**
   - especially in Sirach, where Swete’s numbering can diverge from the
     modern numbering used elsewhere in the repo.
4. **True micro-ambiguity**
   - breathing marks, accents, punctuation, or tiny letterforms that
     remain genuinely hard even on the correct page.

Only the first three are “infrastructure rescue” problems. The fourth is
real residual uncertainty and should not be papered over.

### 4) Run targeted rescue, not a full blind rerun

The main targeted tool is:

- `tools/rescue_manual_pages.py`

Its purpose is to say:

> “For this exact verse, use these exact page images, and adjudicate only
> this local problem.”

That script is the right place for hand-curated rescue targets when a
book has awkward page metadata, alternate numbering, or a short verse
that content-matching handles badly.

### 5) Promote confidence only when the scan supports it

The rule is strict:

- `high` only when the printed reading on the scan is actually visible,
- `medium` when a real small ambiguity remains,
- never promote just because another witness agrees or because the
  answer is “probably obvious.”

This is why some verses stayed medium even after rechecking the exact
page. The project’s honesty layer matters more than a cosmetically
perfect metric.

## The 2026-04-21 rescue results

### Sirach: the final `low` verses were infrastructure failures

The last five `low` verses were solved by correcting the rescue page
targets:

- `SIR 3:5, 3:7` → visible on **vol2 p665**
- `SIR 33:14–16` → visible on **vol2 p728**
- `SIR 33:17` → visible on **vol2 p734**

Before that correction, the rescue had been looking at the wrong pages
and was honestly reporting that the verses were not visible.

Once the true pages were attached, those verses were re-adjudicated from
the scan and promoted from `low` to `high`.

### ADE 4:28: small wording issue, cleanly fixable

`ADE 4:28` was promoted from `medium` to `high` after direct recheck of
**vol2 p784**.

The important point was simple: Swete prints the line **without** `ἐπὶ`
before `τράπεζαν Ἁμάν`. That made the prior medium reading unnecessary.

### 1 Esdras 9 tail block: source-layer realignment

Inspection of the page showed that `1ES 9:35` was not an isolated medium
verse at all. It sat inside a broader late-chapter verse-number drift in
the tail of 1 Esdras 9, introduced by the AI parse for
`parsed_ai/1ES_009.json`.

That problem was later fixed at the **source layer**:

- the affected tail block in `parsed_ai/1ES_009.json` was realigned to
  the raw page parser for pp. 176–177,
- the p. 178 continuation was manually re-transcribed from the scan,
- stale adjudications for the mis-keyed tail span were discarded, and
- the 1ES corpus outputs were regenerated from the corrected source.

The lesson is important: when a residual exposes a whole mis-numbered
span, the right fix is to repair the chapter source and rebuild — not to
paper over one verse at a time.

### Baruch 1:1: final micro-check to 100% high

`BAR 1:1` was the very last remaining `medium` verse. The issue was the
tiny breathing-mark distinction between `Ἀσαδίου` and `Ἁσαδίου`.

The resolution came from a **micro-paleographic crop check** on
**vol3 p374**:

- the page was fetched again at higher resolution,
- the ambiguous word was cropped and enlarged,
- the crop was inspected directly rather than through the full-page
  context alone,
- and the breathing mark proved legible enough to call as smooth.

That promoted `BAR 1:1` from `medium` to `high` and brought the final
corpus to **100% high confidence**.

## Files involved in the rescue loop

These are the main files that matter when doing this work:

- `tools/rescue_manual_pages.py`
- `tools/apply_adjudications.py`
- `tools/generate_master_benchmark.py`
- `tools/generate_quality_benchmark.py`
- `tools/generate_residual_uncertainty.py`
- `sources/lxx/swete/adjudications/*.json`
- `sources/lxx/swete/final_corpus_adjudicated/*.jsonl`
- `sources/lxx/swete/CORPUS_HEALTH.md`
- `sources/lxx/swete/RESIDUAL_UNCERTAINTY.md`

## Repeatable command sequence

With the Azure/OpenAI environment loaded, the normal sequence is:

```bash
python3 tools/rescue_manual_pages.py
python3 tools/apply_adjudications.py
python3 tools/generate_master_benchmark.py
python3 tools/generate_quality_benchmark.py
python3 tools/generate_residual_uncertainty.py
```

Then verify the result in:

- `sources/lxx/swete/final_corpus_adjudicated/`
- `sources/lxx/swete/CORPUS_HEALTH.md`
- `sources/lxx/swete/RESIDUAL_UNCERTAINTY.md`

## Guardrails for future work

- **Do not** promote a verse to `high` because the expected answer is
  “obvious.”
- **Do not** trust `source_pages` blindly; check the actual page image.
- **Do not** patch a single verse when the evidence shows a larger
  verse-number drift.
- **Do** preserve page provenance when a rescue uses a newly verified
  page.
- **Do** regenerate the health and residual docs after every real rescue.

## Bottom line

The final Phase 8 gains did not come from magical extra OCR power. They
came from a disciplined loop:

**residual list → exact page → classify failure → targeted rescue →
honest confidence update**.

That loop is now part of the project’s documented method.
