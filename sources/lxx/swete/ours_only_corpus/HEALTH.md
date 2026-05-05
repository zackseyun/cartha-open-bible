# People's Open Bible — Phase 8 corpus health (our OCR only)

**Generated:** 2026-04-21 13:43 UTC

## Source composition (every verse is our own OCR)

- **Total verses:** 495
- From AI vision parse (GPT-5.4 direct on scan images): **480** (97.0%)
- From regex parser over our transcribed .txt: **15** (3.0%)
- From First1KGreek: **0** (validation-only, never copied)

## Independent validation against First1KGreek

First1KGreek's TEI-XML encoding of the same Swete edition is used
only to check our OCR. A random verse we disagree with is not
automatically assumed wrong — but similarity scores let us see
where our OCR is likely correct vs. where human review is warranted.

- **Text agreement** (similarity ≥ 0.85): 224 (45.3%)
- **Minor mismatch** (0.5 ≤ sim < 0.85): 48 (9.7%) — usually accent/orthographic
- **Major mismatch** (sim < 0.5): 157 (31.7%) — likely our OCR error; human review recommended
- **No reference available**: 66 (13.3%) — First1KGreek has no verse at this key
- **Verses present in First1KGreek but missing from ours**: 1

## Agreement rate on verses both sources contain

**224/429 = 52.2% perfect agreement**, with an additional 11.2% minor variations (accents, spacing) — jointly 63.4% functional agreement.

## Per-book health

| Book | Verses | AI | Regex | Agree | Minor | Major | No ref | Missing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1ES | 495 | 480 | 15 | 224 | 48 | 157 | 66 | 1 |

## Gaps still present

Verses where First1KGreek has content but our OCR produced none.
These need either (a) more page transcription from scans, or (b)
a targeted AI re-parse of specific chapters.

### 1ES (1 missing)

- Ch 5: verses [145]

