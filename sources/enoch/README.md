# 1 Enoch source materials

This directory holds the public-domain source editions for the Cartha
Open Bible's forthcoming 1 Enoch translation. **Scope and strategy:
see [`../../ENOCH.md`](../../ENOCH.md).**

## The textual situation in one paragraph

1 Enoch was originally composed in Aramaic and Hebrew between the 3rd
century BC and the 1st century AD. The Aramaic original is partially
preserved at Qumran (4Q201–212). A Greek translation once existed;
significant fragments survive (Codex Panopolitanus, Syncellus extracts,
Chester Beatty papyri) but are incomplete. The **only complete witness
is the Ethiopic (Ge'ez) translation**, preserved in the Ethiopian
Orthodox tradition and first brought to European scholarship by James
Bruce in 1773. Our primary source is therefore the Ge'ez; the Greek
fragments serve as secondary witnesses where available; the Qumran
Aramaic is consulted via scholarly apparatus (Milik 1976, Zone 2).

## Directory layout

```
sources/enoch/
├── README.md         (this file)
├── MANIFEST.md       SHA-256 hashes + rehydration commands
├── scans/            PDFs of PD source editions (gitignored)
│   ├── charles_1906_ethiopic.pdf
│   ├── dillmann_1851_ethiopic.pdf
│   ├── bouriant_1892_greek.pdf
│   ├── flemming_1901_greek.pdf
│   ├── schodde_1882_english.pdf
│   └── apot_vol2_1913.pdf
├── ethiopic/
│   └── transcribed/  (pending) per-chapter UTF-8 Ge'ez text from our Gemini OCR
├── greek/
│   └── transcribed/  (pending) per-chapter Greek text from OCR of Bouriant + Flemming
└── english_reference/
    └── transcribed/  (pending) Schodde + Charles APOT for verse-numbering reference only
```

## Witness coverage by chapter range

| Chapters | Ge'ez (Charles 1906 + Dillmann 1851 OCR, CC-BY 4.0 our work) | Greek | Qumran Aramaic (Zone 2) |
|---|---|---|---|
| 1–32 | ✓ complete | Panopolitanus (Bouriant 1892) | 4Q201, 4Q202 |
| 33–36 | ✓ complete | — | 4Q204 |
| 37–71 (Parables) | ✓ complete | **none** | **none** |
| 72–82 | ✓ complete | fragments | 4Q208–211 |
| 83–90 | ✓ complete | — | 4Q204–207 |
| 91–108 | ✓ complete | Chester Beatty chs 97-107 (Flemming 1901) | 4Q204, 4Q212 |

Parables (chs 37-71) are Ge'ez-only. This is a known feature of the
textual tradition, not a gap in our pipeline.

## Zone 1 validation oracle (not vendored here)

The Hiob Ludolf Centre / University of Hamburg publishes a TEI XML
digital Ge'ez text of 1 Enoch (`LIT1340EnochE.xml`, ~712 KB) at
https://github.com/BetaMasaheft/Works . Based on Michal Jerabek's
1995 *Library of Ethiopian Texts* digitization, 216 chapter
divisions, ~179,000 Ethiopic characters covering all 108 chapters.

License is ambiguous (CC-BY-SA 4.0 wrapper / NC inner attribution),
so we do NOT vendor it here and do NOT derive our output from it.

**Role**: validation oracle for our own Gemini-OCR of Charles 1906
and Dillmann 1851, analogous to First1KGreek's role for LXX Swete.
A local copy is kept at `~/cartha-reference-local/enoch_betamasaheft/`
on the drafter's workstation.

## Zone 2 consult (scholarly references, not reproduced)

Per [`../../REFERENCE_SOURCES.md`](../../REFERENCE_SOURCES.md), these
copyrighted works are consulted but never reproduced:

- **Milik, *The Books of Enoch: Aramaic Fragments of Qumrân Cave 4*** (DJD XXXVI, 1976) — Qumran 4Q201–212
- **Nickelsburg, *1 Enoch 1*** (Hermeneia, 2001) — chs 1–36, 81–108
- **Nickelsburg & VanderKam, *1 Enoch 2*** (Hermeneia, 2012) — chs 37–71
- **Knibb, *The Ethiopic Book of Enoch*** (Oxford, 1978) — modern critical Ethiopic
- **Black, *The Book of Enoch or 1 Enoch*** (Brill, 1985) — modern English
- **Charlesworth (ed.), OTP vol. 1** (1983, Isaac's translation)

These are named in `tools/enoch/multi_witness.py` (to be written) as
the Zone 2 registry for the Phase 11 translator prompt.

## OCR note

Critical validation result (2026-04-21): **Azure GPT-5 fails on
Ge'ez script** despite handling Greek, Hebrew, and Latin at 98%+
accuracy. **Gemini 2.5 Flash succeeds** on the same pages. The
Enoch OCR pipeline therefore uses Gemini (Flash for bulk, Pro for
rescue/disambiguation), which is different from the LXX / 2 Esdras
pipelines that use Azure GPT-5.

This is a pipeline-level decision, not a quality compromise —
choosing the tool that works for each script.

## Status

**2026-04-21: source acquisition phase.** PDFs vendored, Ge'ez OCR
validated (Gemini 2.5 Flash), Beta maṣāḥǝft oracle archived locally.
Transcription pipeline not yet built. Translation begins after
Phase 10 (2 Esdras) — see `ENOCH.md` for the full phased plan.
