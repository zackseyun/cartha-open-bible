# Cartha Open Bible — Phase 8 corpus health (our OCR only)

**Generated:** 2026-04-20 09:45 UTC

## Source composition (every verse is our own OCR)

- **Total verses:** 6074
- From AI vision parse (GPT-5.4 direct on scan images): **4996** (82.3%)
- From regex parser over our transcribed .txt: **1078** (17.7%)
- From First1KGreek: **0** (validation-only, never copied)

## Independent validation against First1KGreek

First1KGreek's TEI-XML encoding of the same Swete edition is used
only to check our OCR. A random verse we disagree with is not
automatically assumed wrong — but similarity scores let us see
where our OCR is likely correct vs. where human review is warranted.

- **Text agreement** (similarity ≥ 0.85): 3300 (54.3%)
- **Minor mismatch** (0.5 ≤ sim < 0.85): 1023 (16.8%) — usually accent/orthographic
- **Major mismatch** (sim < 0.5): 1231 (20.3%) — likely our OCR error; human review recommended
- **No reference available**: 520 (8.6%) — First1KGreek has no verse at this key
- **Verses present in First1KGreek but missing from ours**: 275

## Agreement rate on verses both sources contain

**3300/5554 = 59.4% perfect agreement**, with an additional 18.4% minor variations (accents, spacing) — jointly 77.8% functional agreement.

## Per-book health

| Book | Verses | AI | Regex | Agree | Minor | Major | No ref | Missing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1ES | 495 | 480 | 15 | 196 | 44 | 189 | 66 | 1 |
| WIS | 444 | 276 | 168 | 272 | 30 | 90 | 52 | 32 |
| SIR | 1406 | 1265 | 141 | 510 | 476 | 374 | 46 | 40 |
| ADE | 216 | 156 | 60 | 72 | 7 | 83 | 54 | 28 |
| JDT | 343 | 321 | 22 | 257 | 41 | 40 | 5 | 1 |
| TOB | 242 | 177 | 65 | 170 | 37 | 23 | 12 | 13 |
| BAR | 159 | 46 | 113 | 40 | 7 | 46 | 66 | 48 |
| ADA | 461 | 404 | 57 | 148 | 62 | 108 | 143 | 90 |
| 1MA | 940 | 687 | 253 | 797 | 98 | 26 | 19 | 0 |
| 2MA | 583 | 464 | 119 | 398 | 57 | 98 | 30 | 0 |
| 3MA | 210 | 155 | 55 | 131 | 29 | 45 | 5 | 22 |
| 4MA | 503 | 493 | 10 | 253 | 120 | 108 | 22 | 0 |
| LJE | 72 | 72 | 0 | 56 | 15 | 1 | 0 | 0 |

## Gaps still present

Verses where First1KGreek has content but our OCR produced none.
These need either (a) more page transcription from scans, or (b)
a targeted AI re-parse of specific chapters.

### 1ES (1 missing)

- Ch 5: verses [145]

### WIS (32 missing)

- Ch 4: verses [21]
- Ch 9: verses [19]
- Ch 17: verses [22, 23, 24, 25, 26, 27, 28, 29]
- Ch 20: verses [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]…

### SIR (40 missing)

- Ch 3: verses [1, 2, 3, 4, 5, 6, 7, 19, 25]
- Ch 13: verses [14]
- Ch 16: verses [15, 16]
- Ch 18: verses [3]
- Ch 26: verses [23, 24, 25, 26, 27]
- Ch 34: verses [28, 29, 30, 31]
- Ch 36: verses [29, 30, 31]
- Ch 40: verses [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]

### ADE (28 missing)

- Ch 4: verses [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
- Ch 8: verses [18, 19, 20, 21, 22, 23, 24]
- Ch 10: verses [4, 5, 6, 7, 8, 9, 10, 11]

### JDT (1 missing)

- Ch 9: verses [19]

### TOB (13 missing)

- Ch 14: verses [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

### BAR (48 missing)

- Ch 1: verses [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
- Ch 2: verses [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]…
- Ch 3: verses [1, 2, 3, 4, 5, 6, 7, 8, 9, 38]

### ADA (90 missing)

- Ch 2: verses [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]…
- Ch 3: verses [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]…

### 3MA (22 missing)

- Ch 1: verses [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]…
- Ch 7: verses [23]

