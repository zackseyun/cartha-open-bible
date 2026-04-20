# Adjudicated corpus — final pass summary

Total verses: **472**
Verses left unchanged (already agreed): **280**
Verses adjudicated against scan: **176**

## Adjudication outcomes

- Our OCR matched scan (kept ours): **127**
- First1KGreek matched scan (Azure verified; we use scan-grounded reading): **24**
- Both equivalent (minor orthography): **3**
- Neither matched scan (fresh scan-based reading): **22**

## Adjudicator confidence

- High: **192**
- Medium: **0**
- Low (may warrant human review): **0**

## Per-book breakdown

| Book | Total | Unchanged | ours→kept | first1k→used | both_ok | neither | High conf |
|---|---:|---:|---:|---:|---:|---:|---:|
| WIS | 472 | 280 | 127 | 24 | 3 | 22 | 192 |

## Attribution note

Every `greek` text in the final corpus is either (a) our original
AI-vision OCR (unchanged from the scan), or (b) a scan-grounded
reading produced by Azure GPT-5.4 looking at the printed Swete
page directly.  First1KGreek's transcription was used only as a
secondary pointer to help the adjudicator focus; no First1KGreek
text was copied into the corpus.  The `pre_adjudication_greek`
field preserves our pre-adjudication reading for audit.
