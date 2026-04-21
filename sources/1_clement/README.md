# 1 Clement source materials

Public-domain source editions for the Cartha Open Bible's Greek
extra-canonical pipeline for **1 Clement**.

Shared scope doc: [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md)

## Textual situation

1 Clement survives in **Greek**, with the most important early witness
traditions associated with Codex Alexandrinus and Codex Hierosolymitanus.
For COB's first pass, the translation anchor will be Greek from
public-domain scholarly editions.

## Local layout

```text
sources/1_clement/
├── README.md
├── MANIFEST.md
├── scans/          local PDFs (gitignored)
└── transcribed/    future OCR / cleaned UTF-8 output
```

## Current local PDFs

- `scans/lightfoot_1889_1clement.pdf`
- `scans/funk_1901_patres_apostolici.pdf`

These are tracked by hash in [`MANIFEST.md`](MANIFEST.md), not in git.

## OCR tool

Use the shared Group A OCR tool:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/1_clement/scans/lightfoot_1889_1clement.pdf \
  --pages 1-5 \
  --out-dir sources/1_clement/transcribed/raw \
  --book-hint "1 Clement — Lightfoot 1889" \
  --stem-prefix 1c_lightfoot1889
```
