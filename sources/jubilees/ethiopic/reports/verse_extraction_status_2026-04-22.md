# Jubilees verse extraction status (2026-04-22)

## Outcome

A full-chapter extraction artifact now exists for Jubilees from the Charles
1895 Ge'ez OCR base.

Current artifact:

- `sources/jubilees/ethiopic/corpus/JUBILEES.vertex.jsonl`

## How it was built

The current file is **hybrid (v3)**:

- deterministic parser where the chapter-aware parser looked reliable
- Vertex AI Gemini fallback where deterministic extraction was obviously too
  sparse

Scripts involved:

- `tools/jubilees/verse_parser.py`
- `tools/jubilees/build_corpus.py`
- `tools/jubilees/build_corpus_vertex.py`

## Coverage snapshot

- chapters represented: **50 / 50**
- current extracted verse records: **1090**
- deterministic chapters: **17**
- Vertex-fallback chapters: **33**

This is a major improvement over the earlier sparse parser-only result, which
left many chapters with zero verse rows.

## Important caveat

This should be treated as a **working extraction artifact**, not yet the final
production corpus.

Why:

- some per-chapter verse counts are still visibly suspicious
- the later-book layout mixes page overlap, chapter-start lines, Ethiopic
  line-start numerals, and apparatus interruptions
- some chapters almost certainly still need better splitting / QA review

So this file is best understood as:

> the first all-chapter Jubilees verse-indexed working corpus,
> not the final adjudicated verse segmentation.

## What it enables right now

Even with those caveats, the project is in a much better place:

- every chapter now has some verse-indexed extraction
- chapter-level drafting / review fixtures can be generated
- the remaining work is concentrated in segmentation QA, not OCR recovery

## Recommended next step

1. spot-audit suspicious chapter counts
2. compare extracted verse ranges against Charles's printed chapter heads and
   surviving line markers
3. then either:
   - promote the hybrid corpus as the current working draft base, or
   - replace weak chapters with improved deterministic / reviewed splits


## Current QA note

Most chapter counts now look plausible. The main obviously low outliers still worth
chapter-specific review are:

- chapter 23 (`9` extracted verses)
- chapter 39 (`5` extracted verses)
