# Phase 8 final corpus provenance

**Generated:** 2026-04-20 07:47 UTC

Total verses: **6110**

- From our OCR + parser (`source: ours`): **4188** (68.5%)
  - Of these, 3907 verified as agreeing with First1KGreek Swete (cross-check passed).
  - 281 verses where First1KGreek had no verse at that location (we went with our reading).
- From First1KGreek Swete (`source: first1kgreek`): **1922** (31.5%)
  - 430 verses where our OCR diverged substantially (similarity < 0.5) — we used First1KGreek.
  - 1492 verses entirely missing from our OCR parse — filled from First1KGreek.

## Attribution

- Our OCR-derived verses are from Swete's _The Old Testament in Greek_ (Cambridge, 1896-1905) scans on Internet Archive, transcribed via GPT-5.4 vision, cross-reviewed against Gemini 2.5 Pro.
- First1KGreek-sourced verses are from `https://github.com/OpenGreekAndLatin/First1KGreek` TEI-XML (CC-BY-SA 4.0), a separately encoded edition of the same Swete text, published by Harvard College Library with funding from the Arcadia Fund.
- Both paths trace to the same underlying scholarly edition (Swete 1909). The First1KGreek-sourced verses are effectively a re-encoding of the same text we OCR'd; they're used here to fill gaps where our vision pipeline had OCR errors or missed verses.

## Per-book breakdown

| Book | Total | Ours (agreed) | Ours (only) | First1K (disagreement) | First1K (missing) |
|---|---:|---:|---:|---:|---:|
| 1ES | 432 | 352 | 2 | 22 | 56 |
| ADE | 235 | 32 | 45 | 48 | 110 |
| JDT | 341 | 294 | 2 | 19 | 26 |
| TOB | 254 | 134 | 11 | 8 | 101 |
| 1MA | 940 | 798 | 19 | 12 | 111 |
| 2MA | 555 | 512 | 2 | 16 | 25 |
| 3MA | 231 | 140 | 4 | 4 | 83 |
| 4MA | 483 | 416 | 2 | 36 | 29 |
| WIS | 476 | 277 | 52 | 90 | 57 |
| SIR | 1419 | 907 | 19 | 164 | 329 |
| BAR | 207 | 45 | 66 | 11 | 85 |
| LJE | 72 | 0 | 0 | 0 | 72 |
| ADA | 465 | 0 | 57 | 0 | 408 |
