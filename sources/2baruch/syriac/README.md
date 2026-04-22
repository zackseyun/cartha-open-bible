# 2 Baruch Syriac primary witness layer

This directory now holds the **bridge layer** between raw OCR pages and future
chapter/verse alignment for the Ceriani 1871 primary Syriac witness.

Current flow:

```text
raw_ocr/ceriani1871/*.txt
  -> tools/2baruch/build_corpus.py
  -> syriac/transcribed/ceriani1871/pages/pXXXX.txt
  -> syriac/transcribed/ceriani1871/page_index.json
  -> syriac/corpus/CERIANI_WORKING.jsonl
```

Important design choice:

- The current committed OCR now covers the **full Ceriani primary sweep** for
  PDF pages 162–228.
- That page corpus has now been tightened into a **chapter-ready source layer** with
  expanded Kmosko control support and no remaining anchorless chapters.
- Some boundary pages are still only medium-confidence (especially inside the epistle
  ladder), but the corpus is now strong enough for chapter-level drafting.

Reading order note:

- Ceriani prints the Syriac in two columns.
- Because Syriac is right-to-left, the logical reading order is:
  **physical right column first, then physical left column**.
- The bridge layer preserves the physical columns separately in JSON, but the text
  files and working corpus use that logical reading order.

## Current milestone

- full Ceriani page corpus on disk
- tentative chapter buckets under `transcribed/ceriani1871/chapters/`
- chapter YAML draft landing zone under `translation/extra_canonical/2_baruch/`

This means 2 Baruch is now **translation-ready at the chapter level**, with the
remaining work narrowed to later spot-checking and finer verse alignment rather than
basic OCR or chapter recovery.
