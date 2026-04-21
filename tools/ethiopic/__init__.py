"""Shared Ethiopic (Geʿez) pipeline infrastructure.

Used by tools/enoch/ and tools/jubilees/ for any work that depends on
reading Ge'ez printed text. Moving this code into one place means:

  1. The Gemini Pro OCR pipeline is written once and improved once.
  2. Ge'ez numeral parsing, word-separator handling, and text
     normalization are consistent across the Ethiopic corpus.
  3. Both books benefit from any upgrade (e.g. a better OCR model
     when one becomes available, a specialist rescue pipeline, etc.).

OCR BACKEND: **Gemini 2.5 Pro** in plaintext mode with low thinking
budget (~512 tokens). Validated 2026-04-21 on Enoch ch 1 against the
Beta maṣāḥǝft ground-truth digital text.

Notably NOT used for Ge'ez:
  - Azure GPT-5: fails entirely — "cannot read" even at 4000px.
  - Gemini 2.5 Flash: hallucinates content (produces Ge'ez Unicode
    characters but the words are not what the scan prints).

Modules (planned):
  - ocr_geez           — Gemini Pro plaintext-mode OCR of a scan page
  - verse_parser       — parse Ge'ez verse markers (፩ ፪ ፫ … ፼)
  - normalize          — light whitespace/punctuation normalization of
                         Gemini output to match Beta maṣāḥǝft-style
                         spacing conventions
  - cross_validate     — diff our OCR against an external oracle
                         (Beta maṣāḥǝft for Enoch; Dillmann-Rönsch
                         for Jubilees)
"""
