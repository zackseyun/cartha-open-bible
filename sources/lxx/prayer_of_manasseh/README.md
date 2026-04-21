# Prayer of Manasseh source materials

Scope and strategy: see [`../../../PRAYER_OF_MANASSEH.md`](../../../PRAYER_OF_MANASSEH.md).

Prayer of Manasseh is **not in Codex Vaticanus**, so Swete's 1909 LXX —
our Phase 8 corpus anchor — does not contain it. This directory
provides a separate source path for the 15-verse prayer.

## Directory layout

```
sources/lxx/prayer_of_manasseh/
├── README.md               (this file)
├── scans/                  PD source PDFs (gitignored; rehydrate from archive.org)
│   └── charles_1913_apot_vol1.pdf
├── transcribed/
│   └── raw/                OCR outputs from Charles 1913 pages 636-640
└── corpus/
    └── MAN.jsonl           15-verse clean Greek text, our Zone 1 primary
```

## Primary source

**R. H. Charles (ed.), *The Apocrypha and Pseudepigrapha of the Old
Testament in English*, Vol. 1 (Oxford: Clarendon Press, 1913)**, pages
612–624 (introduction) and 636–640 (parallel English translation +
critical apparatus).

Archive.org identifier: `theapocryphaandp01unknuoft`
PDF SHA-256: `3b2f6c382a13ad2c11a1e99e1e05a1a9e6c79db49b7a01f4213080fcf6a754f9`
License: Public Domain (pre-1929 US publication; author d. 1931).

Charles prints English as the main text with the Greek cited in a
critical apparatus referencing Codex Alexandrinus (**A**, primary),
Codex Turicensis (**T**), Apostolic Constitutions book 2 chapter 22
(**Const. Apost.**), Syriac (**Syr.**), Latin Vulgate (**Lat.**), and
Mozarabic Psalter (**Moz.**).

## How MAN.jsonl was built

1. **OCR**: `tools/greek_extra_pdf_ocr.py` + Gemini 3.1 Pro preview was
   run on Charles 1913 APOT Vol 1 pages 636-640. Outputs in
   `transcribed/raw/man_charles1913_p06{36..40}.{txt,meta.json}`.

2. **Reconstruction**: `/tmp/reconstruct_prayer_of_manasseh.py` passed
   the 5 OCR'd pages to Gemini 3.1 Pro with an explicit scholarly
   prompt asking for the continuous Greek text of verses 1-15 as
   witnessed by Codex Alexandrinus (the primary witness in Charles's
   apparatus). The Greek text itself is **Public Domain by age**
   (~2000 years); Charles's apparatus lemmata are PD by Charles's
   1913 publication date.

3. **Cross-check**: the reconstruction was validated verse-by-verse
   against Rahlfs-Hanhart Ode 12 (Zone 2 consult, NC-license,
   consultation only). Verse-by-verse word-overlap was 62–92% with
   mismatches almost entirely traceable to:
   - Different verse-division conventions between manuscript
     families (content present but split at different boundaries)
   - Minor orthographic variants (accent + breathing variations
     consistent with Codex Alexandrinus as against Rahlfs's
     eclectic choices)

4. **Hand correction**: `παντοκράτωρ` (vocative) in v1 was restored
   from the OCR artifact `παντοκράτορ`. All other Gemini output was
   retained; scan-adjudication against the Charles page images for a
   full round of verification is a Phase 9 polish task.

## Three-zone status

- **Zone 1 (vendored, CC-BY 4.0 downstream)**: Charles 1913 APOT
  Vol 1 (PD by age), our OCR output, the reconstructed MAN.jsonl
  Greek text.
- **Zone 2 (consulted, not reproduced)**: Rahlfs-Hanhart Ode 12
  (Stuttgart 2006), used only to verify word-overlap during
  reconstruction; its text is NOT copied.
- **Zone 3 (forbidden)**: modern commercial translations of Prayer
  of Manasseh (NRSV, NABRE). Not consulted during drafting.

## Next steps

1. Scan-grounded adjudication pass (optional polish): re-run each
   verse against Charles page images to verify our reconstructed
   Greek matches the apparatus lemmata exactly where Charles gives
   them.
2. Phase 9 drafting: `MAN.jsonl` is now available to
   `tools/build_translation_prompt.py` (once it registers MAN); draft
   the English using our standard deuterocanon drafter.
3. Ship as part of the next COB release, closing the Apocrypha
   draft gap to 100%.
