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
- This bridge still stays **page-level on purpose**. It preserves stable, cleaned
  Syriac page text in logical reading order while deferring chapter/verse mapping
  until the next dedicated segmentation pass.

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

This means 2 Baruch is now **translation-ready at the chapter level**, even
though later control review and finer verse alignment still remain ahead.
