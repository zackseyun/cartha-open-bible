# Didache source materials

Public-domain source editions for the Cartha Open Bible's Greek
extra-canonical pipeline for the **Didache** (*Teaching of the Twelve
Apostles*).

Shared scope doc: [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md)

## Textual situation

The Didache survives primarily in **Greek**, chiefly through the
Codex Hierosolymitanus (Bryennios manuscript tradition). For COB's
first pass, the translation anchor will be Greek from public-domain
scholarly editions.

## Local layout

```text
sources/didache/
├── README.md
├── MANIFEST.md
├── scans/          local PDFs (gitignored)
└── transcribed/    future OCR / cleaned UTF-8 output
```

## Current local PDFs

- `scans/hitchcock_brown_1884.pdf`
- `scans/schaff_1885_oldest_church_manual.pdf`

These are tracked by hash in [`MANIFEST.md`](MANIFEST.md), not in git.

## OCR tool

Use the shared Group A OCR tool:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/didache/scans/hitchcock_brown_1884.pdf \
  --pages 1-5 \
  --out-dir sources/didache/transcribed/raw \
  --book-hint "Didache — Hitchcock & Brown 1884" \
  --stem-prefix didache_hb1884
```
