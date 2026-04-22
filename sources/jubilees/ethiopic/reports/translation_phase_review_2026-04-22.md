# Jubilees translation-phase review (2026-04-22)

## Scope

This review is **Jubilees-only**.

## What was reviewed

### 1. Source readiness

The translation-phase source stack now has:

- full working chapter map (`sources/jubilees/page_map.json`)
- regenerated Charles 1895 Ge'ez body OCR through chapter 50
- working all-chapter verse corpus (`sources/jubilees/ethiopic/corpus/JUBILEES.vertex.jsonl`)
- targeted repair artifacts for formerly weak chapters 23 and 39

### 2. Prompt-builder readiness

`tools/jubilees/build_translation_prompt.py` was updated to prefer the working
Jubilees corpus over ad hoc raw-page reparsing when the corpus is available.

That means translation prompts now anchor to the reviewed working corpus first,
which is the correct behavior for the next drafting phase.

### 3. Spot validation

Representative prompt-build checks passed for:

- Jubilees 1:1
- Jubilees 23:30
- Jubilees 39:17
- Jubilees 50:13

Each loaded from the working corpus layer successfully.

## Current readiness judgment

**Ready to move into Jubilees translation drafting / review work.**

Not because the segmentation is perfect in an absolute sense, but because:

- the OCR blocker is gone
- the chapter-map blocker is gone
- the obvious weak extraction outliers were repaired
- the prompt-builder now consumes the reviewed working corpus rather than raw
  page reparsing

## Remaining risk

The working corpus is still a **working corpus**, not a final fully-adjudicated
segmentation edition. Some chapter boundaries and verse granularity may still
receive later cleanup during drafting/revision.

But that is now normal downstream QA, not a phase-blocking source problem.

## Practical conclusion

For Jubilees specifically, the project can now move on from:

- OCR recovery
- chapter mapping
- glaring weak extraction spots

and into:

- translation drafting
- lexical review
- later segmentation polish where needed


## Deduplication note

A later QA pass found duplicate chapter+verse rows in the working corpus. The corpus was normalized by keeping the strongest row per chapter+verse (targeted refinement > Vertex split > deterministic parser, with longer text as tie-breaker).
