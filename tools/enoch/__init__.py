"""1 Enoch (Mashafa Henok) translation pipeline.

Architecturally separate from tools/ (LXX), tools/2esdras/ (Latin).
The Enoch pipeline is distinct because:

  - Primary source is Ethiopic (Ge'ez), not Greek or Latin
  - OCR backend is Gemini 2.5 (Azure GPT-5 fails on Ge'ez script)
  - Zone 1 validation oracle is the Beta maṣāḥǝft digital TEI XML
    (kept local, not vendored) rather than an in-repo reference
  - Greek fragments (Bouriant, Flemming) provide per-chapter apparatus
    where they survive, but most of Enoch has only Ge'ez attestation

See ENOCH.md for scope + strategy.

Modules (planned):
  - ocr_ethiopic      — Gemini-based OCR of Charles 1906 + Dillmann 1851
  - validate_vs_betamasaheft — cross-check our OCR against the Jerabek
                        1995 Ge'ez digital text (Zone 1 oracle)
  - ocr_greek         — Azure GPT-5 OCR of Bouriant 1892 + Flemming 1901
                        (Greek fragments, same pipeline as our LXX work)
  - multi_witness     — per-verse aggregator: Ge'ez + Greek where
                        available + Zone 2 Qumran-via-Milik registry
  - build_translation_prompt — Phase 11 translator prompt assembly
"""
