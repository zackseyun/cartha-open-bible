"""2 Esdras (4 Ezra) translation pipeline.

Architecturally separate from tools/ (which is LXX-focused). See
2ESDRAS.md for scope and strategy.

Modules (planned):
  - ocr_pipeline    — Azure GPT-5 vision OCR of Violet 1910 scans
  - latin_bensly    — per-verse parser for the Bensly 1895 critical Latin
  - multi_witness   — aggregator returning all 6 daughter-translation
                      readings per verse for the adjudicator/translator
  - build_translation_prompt — Phase 10 translator prompt assembly
"""
