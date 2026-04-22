# Shepherd of Hermas source materials

Public-domain source editions for the Cartha Open Bible's Greek
extra-canonical pipeline for the **Shepherd of Hermas**.

Shared scope doc: [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md)

## Textual situation

The Shepherd of Hermas survives primarily in **Greek**, with important
secondary witness traditions in Latin and Ethiopic. For the first COB
pass, the translation anchor is Greek.

## Local layout

```text
sources/shepherd_of_hermas/
├── README.md
├── MANIFEST.md
├── scans/          local PDFs (gitignored)
└── transcribed/    future OCR / cleaned UTF-8 output
```

## Current local PDFs

- `scans/lightfoot_1891_apostolic_fathers.pdf`

This is tracked by hash in [`MANIFEST.md`](MANIFEST.md), not in git.

## OCR tool

Use the shared Group A OCR tool:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/shepherd_of_hermas/scans/lightfoot_1891_apostolic_fathers.pdf \
  --pages 314-315 \
  --out-dir sources/shepherd_of_hermas/transcribed/raw \
  --book-hint "Shepherd of Hermas — Lightfoot 1891" \
  --stem-prefix hermas_lightfoot1891
```

## Parser / normalized output

Once raw OCR is present, normalize it with:

```bash
python3 tools/shepherd_of_hermas.py --write-normalized
```

That writes:

- `sources/shepherd_of_hermas/transcribed/normalized/*.txt`
- `sources/shepherd_of_hermas/transcribed/unit_map.json`

The parser preserves Lightfoot-style unit identifiers such as `V.3.xiii`,
`M.4.ii`, and `S.5.vi` so later drafter work can target stable Hermas units.
