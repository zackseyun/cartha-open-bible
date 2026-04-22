# 2 Baruch — tentative chapter segmentation

This layer turns the full Ceriani page corpus into **tentative chapter buckets** so
translation can begin before final verse alignment is done.

## Method

- primary substrate: `sources/2baruch/syriac/transcribed/ceriani1871/pages/`
- page order: **PDF 228 -> 162** (book start to book end)
- anchor pages: `chapter_anchors.json`
- interpolation: `page_chapter_ranges.json`
- chapter buckets: `chapter_buckets.json` + `chapters/chNN.*`

## Important warning

These are **translation-prep buckets**, not final critical-edition boundaries.
Boundary pages intentionally overlap between adjacent chapters so no source text is
accidentally dropped before later control-witness review.

## Next refinement path

1. targeted Kmosko control OCR around weak / boundary pages
2. chapter-level review of bucket transitions
3. later verse alignment inside each chapter bucket
