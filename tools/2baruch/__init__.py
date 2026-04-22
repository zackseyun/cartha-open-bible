"""2 Baruch (Syriac Apocalypse of Baruch) translation pipeline.

This sits in the same *family* as tools/2esdras/: a Semitic-apocalypse
multi-witness workflow where the primary surviving witness is a
daughter translation (Syriac here, Latin in 2 Esdras) and secondary
fragments provide apparatus rather than a reconstructed base text.

Modules (planned):
  - ocr_pipeline             — OCR of local PD source scans / bundles (initial Ceriani calibration landed)
  - syriac_primary           — chapter/verse loader for cleaned Syriac
  - multi_witness            — Syriac + Greek/Latin fragment aggregator
  - build_translation_prompt — Phase 15 prompt assembly
"""
