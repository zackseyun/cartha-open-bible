# Phase 9 extra-book audit — unfinished books (2026-04-22)

This note narrows in on the unfinished non-Jubilees Phase 9 / post-Phase-9
extra books that were under discussion on 2026-04-22:

- 1 Enoch
- Psalms of Solomon
- Shepherd of Hermas
- Testaments of the Twelve Patriarchs
- 2 Baruch

Jubilees is intentionally excluded here because it is already in its own
nearly-complete track.

## Short version

### Ready to draft soonest

1. **Psalms of Solomon** — source transcription + parser are done; the main missing
   work is just running the drafter across the remaining corpus and wiring it into
   the chapter queue / public progress surfaces.
2. **1 Enoch** — much farther along than the older scope notes imply. Chapter OCR is
   broadly present for Charles 1906 and Dillmann 1851, but the missing bridge was
   verse-level extraction + a drafter-facing prompt builder.

### Mid-stage

3. **Shepherd of Hermas** — raw Greek OCR coverage exists, but it is still raw page
   text. What is missing is the parser / structure layer that turns those pages into
   Visions / Mandates / Similitudes units or stable chapter/verse units.
4. **Testaments of the Twelve Patriarchs** — early OCR pilot exists, but this is still
   the least mature of the Greek-primary books. Source-layout and parser work remain.

### Earliest-stage

5. **2 Baruch** — OCR pipeline calibration exists for Ceriani, but the real Syriac
   corpus / parser / prompt-builder / drafter stack is still ahead of us.

## Book-by-book

### 1 Enoch

**What already exists**

- `sources/enoch/ethiopic/page_map.json` maps all 108 chapters.
- `sources/enoch/ethiopic/transcribed/charles_1906/ch*.txt` exists for the full book.
- `sources/enoch/ethiopic/transcribed/dillmann_1851/ch*.txt` also exists.
- OCR tooling and validation tooling are already present under `tools/enoch/`.
- Multi-witness registry scaffolding already exists in `tools/enoch/multi_witness.py`.

**What was missing before this audit**

- A reliable **verse parser** for the Charles 1906 OCR.
- A drafter-facing **prompt builder** that could target a specific verse.
- A practical bridge from “chapter OCR exists” to “the drafter can now consume it.”

**Current blockers after this audit**

- Secondary Dillmann verse alignment is still missing.
- Greek-fragment witness integration is still missing.
- Full drafter orchestration script is still missing.
- Some OCR chapter files are visibly partial and will need reruns / cleanup.

**Best next step**

- Finish the Enoch drafter by adding a verse-draft runner that consumes the new
  prompt builder, then selectively rerun weak OCR chapters.

### Psalms of Solomon

**What already exists**

- Full Swete transcription is complete.
- Dedicated parser exists at `tools/psalms_of_solomon.py`.
- The parser already recovers the full 330-verse corpus.
- `PSS` is already present in the Swete deuterocanon registry.
- A few verse YAML drafts already exist under `translation/deuterocanon/psalms_of_solomon/`.

**What is actually missing**

- Not really scaffolding — mostly **draft execution**.
- Chapter queue / automation surfaces have not been initialized for `PSS` yet.
- The public progress snapshot now has a `PSS` row, but the actual draft run still needs
  to be pushed through the remaining 322 verses.

**Best next step**

- Enqueue / run the remaining PSS draft jobs. This is the cleanest “just finish it”
  candidate in the unfinished set.

### Shepherd of Hermas

**What already exists**

- Public-domain source setup is in place under `sources/shepherd_of_hermas/`.
- Raw OCR coverage is much better than the older README implies — many Lightfoot pages
  are already transcribed into `transcribed/raw/`.
- Shared Greek-extra OCR tooling exists.

**What is missing**

- A **structural parser** that turns raw Lightfoot pages into stable book units.
- A decision about the output granularity: Visions / Mandates / Similitudes sections,
  Lightfoot chapter numbers, or another stable citation layer.
- Prompt builder.
- Drafter.

**Best next step**

- Build the structural parser first. Hermas is blocked more by segmentation than by OCR.

### Testaments of the Twelve Patriarchs

**What already exists**

- Source docs and scans are wired up under `sources/testaments_twelve_patriarchs/`.
- A raw Greek OCR pilot exists in `transcribed/raw/`.

**What is missing**

- A robust page map / layout model for the Sinker source.
- Parser logic to split the source into the twelve testaments and their internal units.
- Prompt builder.
- Drafter.

**Best next step**

- Expand OCR coverage enough to settle the source layout, then write the parser.

### 2 Baruch

**What already exists**

- Scope and source docs are in place.
- Source files are rehydrated locally.
- `tools/2baruch/ocr_pipeline.py` exists.
- A first Ceriani OCR calibration batch is already present under `sources/2baruch/raw_ocr/ceriani1871/`.

**What is missing**

- Full primary Syriac OCR.
- Clean chapter-indexed Syriac corpus.
- Multi-witness loader (Ceriani/Kmosko/Violet roles).
- Translation prompt builder.
- Drafter.

**Best next step**

- Finish the Ceriani OCR sweep and build the chapter corpus before attempting any draft tool.

## Recommended order from here

If the goal is to make the biggest forward progress with the least new uncertainty:

1. **Finish Psalms of Solomon drafting**
2. **Complete 1 Enoch drafter wiring**
3. **Build Shepherd of Hermas parser/segmentation**
4. **Build Testaments parser/segmentation**
5. **Finish 2 Baruch OCR-to-corpus bridge**

That order follows the real current state of the repo, not the older planning docs.
