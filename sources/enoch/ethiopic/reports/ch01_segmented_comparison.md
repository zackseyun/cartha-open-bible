# 1 Enoch chapter 1 — segmented OCR comparison

## What was tested
- **Full-page OCR** on Charles 1906 page 40 (baseline)
- **Segmented OCR, bands_v1** on Charles 1906 page 40
- **Segmented OCR, bands_v1** on Charles 1906 page 42 (output only; no scan-truth set yet)

## Result
- **Full-page baseline (p40, verses 1–5): 63.07%** normalized character accuracy
- **Segmented bands_v1 (p40, verses 1–5): 57.54%** normalized character accuracy
- **Delta:** segmented pass is **5.53 percentage points worse** than the full-page baseline

## Interpretation
The first segmented rescue pass did **not** improve Charles page 40.

This does not prove segmentation is useless, but it does show that a naive
three-band strategy is not yet the fix. The current evidence is:

1. Beta maṣāḥǝft-over-BM comparison overstated OCR failure because it mixed
   in edition variance.
2. But even against scan-grounded truth, the current full-page OCR is only
   moderate (~63%).
3. Same-source rerun agreement is poor (~46%), which points to real model
   instability on dense Ethiopic pages.
4. The first segmentation strategy (bands_v1) made the page worse rather than
   better.

## Practical next move
The next rescue step, if pursued, should probably be **more targeted than
coarse bands** — for example:

- explicit body-line segmentation,
- apparatus masking before OCR,
- or a two-stage pipeline where one pass detects verse lines and a second pass
  OCRs each detected line/region.

Coarse page bands alone are not enough.
