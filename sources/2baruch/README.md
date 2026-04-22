# 2 Baruch (Syriac Apocalypse of Baruch) source materials

Public-domain source editions for the Cartha Open Bible's forthcoming
2 Baruch translation. **Scope and strategy: see
[`../../2BARUCH.md`](../../2BARUCH.md).**

## Textual situation

2 Baruch was likely composed in Hebrew or Aramaic soon after 70 CE,
then passed through a Greek stage before surviving in full in
**Syriac**. That means the Syriac is our primary witness, just as the
Latin is primary for 2 Esdras. Greek fragments and the tiny Latin
remnant matter for apparatus, but they do not replace the Syriac as
our translation base.

## Directory layout

```
sources/2baruch/
├── README.md                     (this file)
├── MANIFEST.md                   SHA-256 hashes + rehydration commands
├── scans/                        local source files (gitignored)
│   ├── ceriani_1871_monumenta_tom5.pdf
│   ├── kmosko_1907_patrologia_syriaca_vol1_2.pdf
│   └── violet_1924_gcs32_wbc.zip
├── reference/
│   └── charles_1896_apocalypse_of_baruch.pdf
├── raw_ocr/                      page-level OCR dumps (Ceriani full sweep now present)
└── syriac/
    ├── README.md                  bridge-layer notes for the primary Syriac witness
    ├── transcribed/              cleaned page-level Ceriani text + page index
    └── corpus/                   working JSONL corpus derived from the bridged OCR
```

Translation drafts will eventually land under
`translation/extra_canonical/2_baruch/` as chapter-level YAML, in the
same general pattern that `translation/extra_canonical/2_esdras/` uses
now.

## Local source files and roles

| File | Edition | Year | Role | Notes |
|---|---|---|---|---|
| `scans/ceriani_1871_monumenta_tom5.pdf` | Ceriani, *Apocalypsis Baruch syriace* in *Monumenta sacra et profana* 5.2 | 1871 | **Primary Syriac base text** | syri.ac cites pp. 113-180 inside the broader `Monumenta... tom. V` scan |
| `scans/kmosko_1907_patrologia_syriaca_vol1_2.pdf` | Kmosko, *Liber Apocalypseos Baruch filii Neriae translatus de graeco in syriacum* in *Patrologia Syriaca* 1.2 | 1907 | **Secondary Syriac / Latin witness** | syri.ac cites cols. 1056-1207 |
| `scans/violet_1924_gcs32_wbc.zip` | Violet, *Die Apokalypsen des Esra und des Baruch in deutscher Gestalt* (GCS 32) | 1924 | Orientation / structure witness | WBC export bundle; contains `index.djvu` + 488 page DjVu files rather than a normalized PDF |
| `reference/charles_1896_apocalypse_of_baruch.pdf` | Charles, *The Apocalypse of Baruch* | 1896 | English numbering / orientation only | never used as translation base |

## Witness roles

| Witness | Language | Coverage | COB role | Local source |
|---|---|---|---|---|
| Ceriani 1871 | Syriac | Complete | Primary translation base | `scans/ceriani_1871_monumenta_tom5.pdf` |
| Kmosko 1907 | Syriac + Latin scholarly witness | Complete | Secondary control witness / apparatus aid | `scans/kmosko_1907_patrologia_syriaca_vol1_2.pdf` |
| Violet 1924 | German with source-language citations | Complete | Structural orientation, division of visions, numbering cross-check | `scans/violet_1924_gcs32_wbc.zip` |
| Charles 1896 | English | Complete | Orientation only | `reference/charles_1896_apocalypse_of_baruch.pdf` |
| Greek fragments + Latin remnant | Greek / Latin | Partial | Future apparatus layer | not yet vendored |

## OCR notes

A quick visual probe of the local files already clarifies the first OCR
pass:

- **Ceriani** is the first real OCR target. Its Baruch pages are mostly
  **two Syriac columns with Latin apparatus at the foot of the page**.
  The first live calibration showed that naive whole-page OCR
  under-transcribed the layout, so the current `tools/2baruch/ocr_pipeline.py`
  uses a **region-assembled pass** (running head + both Syriac columns + both
  apparatus crops) for Ceriani pages.
- **Kmosko** is mostly **Latin scholarly discussion with inline Syriac**
  forms. It is valuable as a control witness, but not the first page
  family to optimize for.
- **Violet 1924 is not the 1910-style parallel witness edition.** The
  accessible copy is a German-form GCS volume; for Baruch, the table of
  contents places the relevant section at pp. 205-336, with the epistle
  beginning at p. 321 and Gressmann's proposals at p. 337.

So the practical start sequence is:

1. Ceriani full primary sweep
2. Tentative chapter segmentation over the page corpus
3. Kmosko targeted control pages
4. Violet structural / numbering extraction

## Zone 2 consult (not reproduced)

Per [`../../REFERENCE_SOURCES.md`](../../REFERENCE_SOURCES.md), the
usual consult-only modern critical editions / commentaries still apply
here. The local source stack above is only the public-domain Zone 1
layer.

## Status

**2026-04-22: full Ceriani primary OCR sweep + bridge layer landed.**
The local source files are rehydrated and pinned in `MANIFEST.md`, the
Ceriani OCR pipeline is working, and `raw_ocr/ceriani1871/` now covers
the full primary-text span at **PDF pages 162–228 inclusive**. The
pilot-page apparatus rescue was retained inside that full sweep, and the
resulting page corpus now also flows through `tools/2baruch/build_corpus.py`
into a committed Syriac bridge layer:

- `sources/2baruch/syriac/transcribed/ceriani1871/pages/`
- `sources/2baruch/syriac/transcribed/ceriani1871/page_index.json`
- `sources/2baruch/syriac/corpus/CERIANI_WORKING.jsonl`

That bridge intentionally stays page-level for now: the OCR substrate is
now complete, but chapter alignment is still the next real task rather
than something to pretend is already done.

See also:
- [`raw_ocr/ceriani1871/COVERAGE.md`](raw_ocr/ceriani1871/COVERAGE.md)
- [`raw_ocr/ceriani1871/SPOTCHECK_QUEUE.md`](raw_ocr/ceriani1871/SPOTCHECK_QUEUE.md)
- [`raw_ocr/kmosko1907/CONTROL_PAGES.md`](raw_ocr/kmosko1907/CONTROL_PAGES.md)
- [`CONTROL_WITNESSES.md`](CONTROL_WITNESSES.md)
- [`syriac/transcribed/ceriani1871/CHAPTER_SEGMENTATION.md`](syriac/transcribed/ceriani1871/CHAPTER_SEGMENTATION.md)
