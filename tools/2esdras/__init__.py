"""2 Esdras (4 Ezra) translation pipeline.

Architecturally separate from tools/ (which is LXX-focused). See
2ESDRAS.md for scope and strategy.

Modules (planned):
  - ocr_pipeline    — Azure GPT-5 vision OCR of Bensly/Violet local PDFs
                      into per-page raw OCR text + provenance sidecars
  - extract_bensly_body — strip `[BODY]` sections from raw OCR into a
                      cleaner Latin working text for chapter cleanup
  - segment_bensly_chapters — split the 1895 BODY-only working text
                      into chapter candidate files with page spans
  - build_missing_fragment_verses — turn the 1875 Missing Fragment into
                      a verse-indexed VII 36–105 working file
  - build_ch07_hybrid — assemble a single cleanup-oriented chapter VII
                      working file from 1895 + 1875 materials
  - latin_bensly    — chapter/verse loader for cleaned Bensly Latin
  - multi_witness   — aggregator returning all 6 daughter-translation
                      readings per verse for the adjudicator/translator
  - build_translation_prompt — Phase 10 translator prompt assembly
"""
