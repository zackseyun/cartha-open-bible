# 2 Baruch — control witnesses and truth-check plan

This note records how the 2 Baruch OCR / cleanup pass should be
adjudicated once the primary Ceriani sweep is on disk.

## Primary / control hierarchy

1. **Ceriani 1871** — primary Syriac base text
2. **Kmosko 1907** — secondary Syriac / Latin scholarly control witness
3. **Violet 1924 (GCS 32)** — structure / division / orientation witness
4. **Charles 1896** — English numbering / orientation only

The governing rule is simple: **Ceriani stays primary.** The other
witnesses help detect OCR mistakes, line-loss, chapter-boundary issues,
and apparatus misunderstandings; they do not replace the primary Syriac
base text.

## Ceriani PDF span for the apocalypse proper + epistle

In the local Google scan of `ceriani_1871_monumenta_tom5.pdf`, the
relevant 2 Baruch body pages run approximately:

- **PDF 162–228** — main Syriac text pages
- **PDF 229** — title / introductory page (`APOCALYPSIS BARUCH SYRIACE`)
- **PDF 230** — blank / terminal page

Empirical page-number relation from the scan body:

- `printed_page + pdf_page ≈ 342`

That mapping is good enough for operational work on this scan and can be
used to relate Ceriani's cited printed span (`pp. 113–180`) to the local
PDF page numbers.

## What to compare once segmentation starts

### 1. Chapter breaks / structural breaks
Use:
- Ceriani running heads + inline Syriac numerals / section markers
- Violet 1924 for vision / epistle structure
- Charles 1896 for chapter numbering sanity checks

### 2. Unclear Syriac body lines
Use:
- Ceriani neighboring pages first
- Kmosko 1907 control page(s) second
- Charles 1896 only to check whether a catastrophic omission probably
  occurred, never as wording authority

### 3. Apparatus-heavy uncertainty
Use:
- Ceriani apparatus (primary local evidence)
- Kmosko 1907 for the same passage family when available

## Spot-check triggers

Prioritize later spot-checking where any of these occur:

- unusually low `output_chars` relative to surrounding pages
- missing or clearly malformed running heads near a suspected chapter edge
- empty / near-empty apparatus on pages that visually appear to carry notes
- repeated OCR nonsense across both Syriac columns on the same page
- abrupt chapter / section transitions that do not fit Charles/Violet

## Practical next step after the full sweep

After the Ceriani primary OCR sweep finishes, the next best move is:

1. build a page-level coverage / anomaly report
2. segment the primary Syriac into tentative chapter buckets
3. run **targeted** Kmosko control OCR only where the Ceriani substrate is
   weak or structurally ambiguous

That gives the highest truth-per-minute ratio. Full-book Kmosko OCR is
not the first bottleneck; **Ceriani segmentation is.**
