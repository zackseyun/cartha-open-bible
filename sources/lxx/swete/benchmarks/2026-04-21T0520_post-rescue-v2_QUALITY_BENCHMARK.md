# Cartha Open Bible — Phase 8 corpus quality benchmark

**Generated:** 2026-04-21 12:20 UTC

## Pipeline stages

Our Phase 8 corpus went through multiple quality passes. This
table shows the trajectory — where we started, and where each
automated pass landed us — measured against First1KGreek's
independent scholarly encoding of the same Swete edition as a
validation oracle (NOT as a source of our text).

| Stage | Verses | Coverage | Agree | Agree+Minor | Major | Missing |
|---|---:|---:|---:|---:|---:|---:|
| 4. AI-vision re-parse (our-OCR-only) | 6074 | 104.2% | 59.4% | 77.8% | 1231 | 275 |
| 5. Scan-adjudicated (final) | 6337 | 108.7% | 72.3% | 86.2% | 803 | 12 |

## Final stage — per-book detail (5. Scan-adjudicated (final))

| Book | Ours | First1K | Agree | Functional | Major | Missing |
|---|---:|---:|---:|---:|---:|---:|
| 1ES | 496 | 430 | 68.6% | 78.6% | 92 | 0 |
| 1MA | 940 | 921 | 92.8% | 98.3% | 16 | 0 |
| 2MA | 583 | 553 | 80.7% | 85.4% | 81 | 0 |
| 3MA | 232 | 227 | 85.5% | 88.5% | 26 | 0 |
| 4MA | 503 | 481 | 80.7% | 95.4% | 22 | 0 |
| ADA | 551 | 408 | 64.5% | 76.2% | 97 | 0 |
| ADE | 244 | 190 | 72.6% | 75.8% | 46 | 0 |
| BAR | 207 | 141 | 92.9% | 100.0% | 0 | 0 |
| JDT | 343 | 339 | 85.8% | 92.3% | 26 | 1 |
| LJE | 72 | 72 | 87.5% | 98.6% | 1 | 0 |
| SIR | 1439 | 1400 | 45.1% | 78.8% | 295 | 7 |
| TOB | 255 | 243 | 85.6% | 95.5% | 11 | 0 |
| WIS | 472 | 424 | 72.9% | 78.6% | 90 | 4 |

## Legend

- **Verses**: total verses in our corpus
- **Coverage**: our verses / First1KGreek verses (how much of their
  complete-encoding corpus we cover)
- **Agree**: % of verses both sources have where our text is ≥85% word-overlap similar
  to First1KGreek (perfect agreement after accent normalization)
- **Agree+Minor**: % where our text is ≥50% similar (functional
  agreement — orthographic variations)
- **Major**: count of verses where our text < 50% similar (real
  textual differences — could be OCR error OR legitimate
  Swete-vs-eclectic text-tradition difference)
- **Missing**: verses First1KGreek has but our corpus lacks

## Interpretation

Agreement does NOT mean First1KGreek is ground truth. They are
also machine-assisted transcription of Swete. Disagreements can
mean:
  - Our OCR error (their reading is right → we should fix)
  - Their encoding error (our reading is right → theirs is wrong)
  - Legitimate textual-tradition difference (both valid, our
    choice is explicit)

The adjudicator pass (final stage) uses Azure GPT-5.4 vision to
look at the actual Swete scan and decide per-verse what the
printed page ACTUALLY says. That's the ground-truth layer on
top of both transcriptions.
