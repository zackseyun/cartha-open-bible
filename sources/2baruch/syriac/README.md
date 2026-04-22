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

- The current committed OCR is only a **sparse calibration set**, not a continuous
  full-book sweep.
- So this bridge is **page-level on purpose**. It preserves stable, cleaned Syriac
  page text in logical reading order while deferring chapter/verse mapping until the
  OCR coverage is broader.

Reading order note:

- Ceriani prints the Syriac in two columns.
- Because Syriac is right-to-left, the logical reading order is:
  **physical right column first, then physical left column**.
- The bridge layer preserves the physical columns separately in JSON, but the text
  files and working corpus use that logical reading order.
