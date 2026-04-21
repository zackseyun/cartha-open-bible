# Adjudicated corpus — final pass summary

Total verses: **6337**
Verses left unchanged (already agreed): **3674**
Verses adjudicated against scan: **2295**

## Adjudication outcomes

- Our OCR matched scan (kept ours): **1291**
- First1KGreek matched scan (GPT-5.4 verified; we use scan-grounded reading): **512**
- Both equivalent (minor orthography): **66**
- Neither matched scan (fresh scan-based reading): **426**

## Adjudicator confidence

- High: **2608**
- Medium: **55**
- Low (may warrant human review): **0**

## Per-book breakdown

| Book | Total | Unchanged | ours→kept | first1k→used | both_ok | neither | High conf |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1ES | 496 | 258 | 98 | 64 | 14 | 50 | 238 |
| ADE | 244 | 123 | 38 | 53 | 3 | 12 | 106 |
| JDT | 343 | 260 | 33 | 16 | 1 | 26 | 83 |
| TOB | 255 | 180 | 33 | 15 | 0 | 11 | 74 |
| 1MA | 940 | 813 | 51 | 19 | 4 | 33 | 126 |
| 2MA | 583 | 426 | 85 | 34 | 2 | 19 | 157 |
| 3MA | 232 | 135 | 14 | 36 | 13 | 18 | 97 |
| 4MA | 503 | 272 | 67 | 79 | 7 | 53 | 231 |
| WIS | 472 | 280 | 127 | 24 | 3 | 22 | 192 |
| SIR | 1439 | 533 | 595 | 75 | 18 | 126 | 891 |
| BAR | 207 | 106 | 9 | 27 | 1 | 2 | 96 |
| LJE | 72 | 56 | 7 | 5 | 0 | 3 | 16 |
| ADA | 551 | 232 | 134 | 65 | 0 | 51 | 301 |

## Attribution note

Every `greek` text in the final corpus is either (a) our original
AI-vision OCR (unchanged from the scan), or (b) a scan-grounded
reading produced by GPT-5.4 looking at the printed Swete
page directly.  First1KGreek's transcription was used only as a
secondary pointer to help the adjudicator focus; no First1KGreek
text was copied into the corpus.  The `pre_adjudication_greek`
field preserves our pre-adjudication reading for audit.
