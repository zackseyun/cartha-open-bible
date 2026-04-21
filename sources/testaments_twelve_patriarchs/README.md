# Testaments of the Twelve Patriarchs source materials

Public-domain source editions for the Cartha Open Bible's Greek
extra-canonical pipeline for the **Testaments of the Twelve Patriarchs**.

Shared scope doc: [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md)

## Textual situation

The Testaments survive primarily in **Greek**, with important secondary
versions in Armenian, Slavonic, and other traditions. For the first COB
pass, the goal is a Greek-primary workflow.

## Current source state

We currently have:

- a **Greek-primary candidate edition**:
  `scans/sinker_1879_testamenta_xii_patriarcharum.pdf`
- an **English reference translation**:
  `scans/charles_1908_testaments.pdf`

The Greek-primary source is no longer just theoretical: the shared OCR
tool has already produced a successful raw Greek pilot from Sinker 1879
(`transcribed/raw/t12p_sinker1879_p0050.txt`).

## Local layout

```text
sources/testaments_twelve_patriarchs/
├── README.md
├── MANIFEST.md
├── scans/          local PDFs (gitignored)
└── transcribed/    future OCR / cleaned UTF-8 output
```

## OCR tool

Use the shared Group A OCR tool:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/testaments_twelve_patriarchs/scans/sinker_1879_testamenta_xii_patriarcharum.pdf \
  --pages 1-3 \
  --out-dir sources/testaments_twelve_patriarchs/transcribed/raw \
  --book-hint "Testaments of the Twelve Patriarchs — Sinker 1879" \
  --stem-prefix t12p_sinker1879
```
