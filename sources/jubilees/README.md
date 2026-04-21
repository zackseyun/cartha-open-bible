# Jubilees (Mashafa Kufale) source materials

Public-domain source editions for the Cartha Open Bible's forthcoming
Jubilees translation. **Scope and strategy: [`../../JUBILEES.md`](../../JUBILEES.md).**

## Textual situation

Jubilees was composed in Hebrew c. 160-150 BC as a retelling of
Genesis 1 through Exodus 14 organized around the 49-year "jubilee"
cycle. The Hebrew original survived in fragments at Qumran (4Q216-228,
recovered in DJD XIII, 1994 — Zone 2). A Greek translation once
existed (cited by Syncellus and Byzantine chronographers) but is
lost. A Latin translation of roughly half the book (chs 13-49)
survives in a single 5th/6th-century palimpsest and was critically
edited by Rönsch in 1874. The only complete witness is the **Ethiopic
(Ge'ez)** translation, preserved in the Ethiopian Orthodox tradition
and first critically edited by Charles 1895.

## Directory layout

```
sources/jubilees/
├── README.md         (this file)
├── MANIFEST.md       SHA-256 hashes + rehydration commands
├── scans/            PDFs of PD source editions (gitignored)
│   ├── charles_1895_ethiopic.pdf
│   ├── charles_1902_english.pdf
│   └── dillmann_ronsch_1874_composite.pdf
├── ethiopic/
│   └── transcribed/  (pending) per-chapter UTF-8 Ge'ez from our Gemini Pro OCR
├── latin/
│   └── transcribed/  (pending) Rönsch 1874 Latin fragments (chs 13-49)
└── english_reference/
    └── transcribed/  (pending) Charles 1902 for verse-numbering reference only
```

## Witness coverage by chapter range

| Chapters | Ge'ez (Charles 1895 OCR, CC-BY 4.0 our work) | Latin (Rönsch 1874) | Qumran Hebrew (Zone 2, via VanderKam-Milik) |
|---|---|---|---|
| 1–12 | ✓ | — | 4Q216-217 partial |
| 13–49 | ✓ | **✓ (Rönsch)** | 4Q219-228 scattered |
| 50 | ✓ | ✓ | — |

Chapters 13-49 have the strongest multi-witness coverage because
the Latin fragments align with much of the Qumran Hebrew material.

## Zone 2 consult (scholarly, not reproduced)

Per [`../../REFERENCE_SOURCES.md`](../../REFERENCE_SOURCES.md):

- **VanderKam & Milik, *DJD XIII: Qumran Cave 4 VIII: Parabiblical Texts Part 1*** (1994) — Hebrew Jubilees fragments 4Q216-228
- **VanderKam, *The Book of Jubilees*** (CSCO 510-511, 1989) — modern critical Ethiopic edition + English translation
- **Segal, *The Book of Jubilees: Rewritten Bible, Redaction, Ideology and Theology*** (Brill, 2007)
- **Wintermute, "Jubilees" in OTP vol. 2 (Charlesworth, ed.)** (1985)

Consulted during translation; never reproduced.

## OCR pipeline

Same Ge'ez pipeline as Enoch: Gemini 2.5 Pro in plaintext mode with
low thinking budget. Validated on Enoch ch 1 (2026-04-21) at
character-level accuracy matching Beta maṣāḥǝft's ground-truth
digital text. Azure GPT-5 (our LXX backend) fails on Ge'ez;
Gemini 2.5 Flash hallucinates content.

No Beta maṣāḥǝft-style digital Ge'ez oracle exists for Jubilees
specifically, so our OCR cross-check relies on the two PD scholarly
editions (Charles 1895 + Dillmann-Rönsch 1874) as mutual checks.

## Status

**2026-04-21: source acquisition phase.** PDFs vendored, OCR pipeline
validated (from Enoch work). Transcription begins after Phase 11
(Enoch) is underway — the shared `tools/ethiopic/` infrastructure
gets built during Enoch and reused here.
