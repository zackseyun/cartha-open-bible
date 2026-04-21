# Changelog

All phase releases are documented here. Individual verse revisions are
tracked in git history on the per-verse YAML files.

## Unreleased

- Repository scaffold
- DOCTRINE.md, METHODOLOGY.md first drafts
- Per-verse YAML schema defined (`schema/verse.schema.json`)

## Extra-canonical corpus scope commitment — 2026-04-21

Scope-expansion document committing the Cartha Open Bible to
translating 11 extra-canonical texts under CC-BY 4.0 beyond the
13 LXX deuterocanonical books of Phase 8. New master scope doc
`EXTRA_CANONICAL.md` catalogs:

- **Tier 1 (historical canonical status somewhere)**: 2 Esdras,
  1 Enoch, Jubilees, Psalms of Solomon.
- **Tier 2 (Apostolic Fathers + pseudepigrapha)**: Didache,
  1 Clement, Shepherd of Hermas, 2 Baruch, Testaments of the
  Twelve Patriarchs.
- **Tier 3 (early Christian mystical/contemplative, with framing)**:
  Gospel of Thomas, Gospel of Truth, Thunder Perfect Mind. Three
  Nag Hammadi texts that do not articulate a cosmologically
  disruptive Gnostic framework: Thomas is a sayings collection,
  Truth is Valentinian contemplation without demiurge cosmology,
  Thunder is a paradoxical divine-feminine monologue.
- **Explicitly held out (open to reconsider)**: Apocryphon of John
  and Gospel of Philip, on account of their explicit demiurge /
  Valentinian sacramental frameworks.

Pipeline groupings (A = LXX Greek infra reuse, B = 2 Esdras
multi-witness reuse, C = new Ethiopic, D = new Coptic) and phased
rollout (Phases 10-16 after Phase 9) documented in
`EXTRA_CANONICAL.md`.

README and DEUTEROCANONICAL.md updated with the new extra-canonical
section and cross-links between scope docs.

## Phase 8e — Psalms of Solomon source setup (in progress, 2026-04-21)

Focused extra-canonical Greek track for **Psalms of Solomon**, using
the existing Swete infrastructure rather than a new source pipeline.

- **Swete transcription completed** for the book's full page span in
  vol. III: `vol3_p0788`–`vol3_p0810`
- **Boundary clarified**: page 811 is the transition away from Psalms
  of Solomon into Enoch appendix material and is **not** part of the
  book's source range
- **Dedicated scope doc** added at `PSALMS_OF_SOLOMON.md`
- **Helper scaffold** added at `tools/psalms_of_solomon.py` to expose
  page range + transcription completeness while the book-specific
  parser is built
- **Page index corrected**: `sources/lxx/swete/transcribed/page_index.json`
  now records the actual Psalms-of-Solomon span (`788-810`) instead of
  the earlier rough probe estimate

## Phase 8f — shared Greek extra-canonical pipeline setup (in progress, 2026-04-21)

Group A infrastructure work for the extra-canonical texts that can
reuse our Greek OCR / transcription stack: **Didache, 1 Clement,
Shepherd of Hermas, Testaments of the Twelve Patriarchs**, with
Psalms of Solomon as the already-exercised Swete-side pilot.

- **Group scope doc** at `GREEK_EXTRA_CANONICAL.md`: defines the shared
  Greek pipeline, explains why these texts belong together, and lays
  out the practical work order across Phase 13 / 14.
- **Shared local-PDF OCR tool** at `tools/greek_extra_pdf_ocr.py`:
  generic Azure GPT-5 Greek OCR for public-domain local PDFs outside
  the Swete corpus.
- **Shared prompt** at
  `tools/prompts/transcribe_greek_extra_generic.md` for late-19th /
  early-20th century Greek scholarly editions.
- **Planned source tree** documented at `sources/greek_extra/README.md`
  for Didache, 1 Clement, Shepherd of Hermas, and Testaments of the
  Twelve Patriarchs.
- **Didache + 1 Clement source manifests** added:
  - `DIDACHE.md`
  - `FIRST_CLEMENT.md`
  - `sources/didache/README.md` + `MANIFEST.md`
  - `sources/1_clement/README.md` + `MANIFEST.md`
  - `.gitignore` updated so the local source PDFs stay out of git while
    their hashes and edition metadata remain documented
- **1 Clement OCR pilot started**:
  - Funk 1901 selected as the practical first OCR source
  - page `260` confirmed the transition into 1 Clement
  - pages `261, 263, 265, …, 343` now capture the Greek text through
    the end of *1 Clement I* in Funk 1901
  - adjacent even pages confirmed the source layout as interleaved
    Latin translation / notes
  - helper scaffold added at `tools/first_clement.py`
  - normalization tooling added at `tools/first_clement_normalize.py`
  - prompt builder added at `tools/build_first_clement_prompt.py`
  - normalized chapter files now exist for chapters `1–65`
  - chapter `42` and the full start of chapter `43` are currently
    filled from a documented supplemental public digital Greek source,
    pending future direct OCR recovery
  - helper fetcher added at `tools/fetch_first_clement_supplements.py`
- **Didache OCR pilot completed** via `tools/greek_extra_pdf_ocr.py`
  on Hitchcock & Brown 1884 pages 16 and 20, writing initial raw OCR
  outputs into `sources/didache/transcribed/raw/`
- **Didache OCR model choice tested** on the same pilot pages:
  Azure GPT-5.4 produced the cleaner primary OCR output; Gemini Pro is
  retained as a useful reviewer / spot-checker rather than the primary
  pass
- **Didache Hitchcock Greek span pushed much further**:
  raw OCR now exists for pages 16, 18, 20, 22, 24, 26, 28, 30, 32,
  34, 36, 38, 40, and 42
- **Normalization tooling added and exercised**:
  - `tools/didache_normalize.py` assembles the raw OCR into chapter
    files
  - `tools/didache.py` loads the normalized chapter files
  - normalized outputs now exist at
    `sources/didache/transcribed/ch01.txt` … `ch16.txt` plus
    `chapter_map.json`
- **Didache prompt-builder added**:
  - `tools/build_didache_prompt.py`
  - builds a chapter-level translation prompt from the normalized
    source layer, doctrine excerpt, philosophy excerpt, and source
    provenance
- **Didache drafting started**:
  - `tools/draft_didache.py`
  - first chapter draft written to
    `translation/extra_canonical/didache/001.yaml`
- **Didache first-pass draft completed**:
  - chapters `001.yaml` through `016.yaml` now exist under
    `translation/extra_canonical/didache/`
  - first-pass quality skim completed during drafting against the
    normalized Greek source layer
- **Shepherd of Hermas + Testaments source trees** added:
  - `sources/shepherd_of_hermas/README.md` + `MANIFEST.md`
  - `sources/testaments_twelve_patriarchs/README.md` + `MANIFEST.md`
  - `.gitignore` updated to keep these local source PDFs out of git
  - local PDFs fetched / recorded for Hermas and for a Greek-primary
    Testaments candidate plus English reference
- **Hermas OCR pilot completed** via `tools/greek_extra_pdf_ocr.py`
  on Lightfoot 1891 pages 314–315, writing initial raw Greek OCR into
  `sources/shepherd_of_hermas/transcribed/raw/`
- **Testaments OCR pilot completed** via `tools/greek_extra_pdf_ocr.py`
  on Sinker 1879 page 50, confirming the Greek-primary candidate is
  usable for raw OCR work and writing initial output into
  `sources/testaments_twelve_patriarchs/transcribed/raw/`

## Phase 8d — Jubilees pipeline + Ge'ez OCR correction (2026-04-21)

Extends the Ethiopic track started in Phase 8c to include Jubilees
alongside Enoch. Also records a significant OCR finding that changes
our earlier Enoch conclusion.

**OCR correction (Ge'ez)** — proper accuracy test against Beta maṣāḥǝft
ground truth shows the earlier "Flash succeeds" claim was premature:

- Azure GPT-5: fails (unchanged)
- **Gemini 2.5 Flash: produces Ge'ez Unicode but hallucinates content.**
  Not usable for production.
- Gemini 2.5 Pro in JSON mode: hits MAX_TOKENS at 32K (Unicode-escape
  overhead). Not usable as-is.
- **Gemini 2.5 Pro in plaintext mode with 512 thinking budget:
  SUCCEEDS at scholarly quality.** Enoch ch 1 test matched Beta
  maṣāḥǝft character-accurately, with remaining differences tracking
  real Dillmann-vs-Jerabek manuscript-family variants. ~1,200 output
  tokens per page.

JSON-mode escaping inflates each 3-byte Ethiopic character to 6
response tokens; a single dense page overflows Pro's 32K output
budget. Plaintext fits comfortably.

**Jubilees source PDFs vendored** in `sources/jubilees/` (gitignored,
MANIFEST tracks SHA-256):
  - Charles 1895 Ethiopic (PD, critical, 4 MSS) -- Zone 1 primary
  - Charles 1902 English (PD) -- reference
  - Dillmann & Rönsch 1874 (PD) -- German translation + Rönsch's
    recovered Latin fragments (chs 13-49) as second witness

**Shared Ethiopic pipeline** `tools/ethiopic/` now includes
`ocr_geez.py`, a resumable batch OCR CLI that renders PDF pages,
calls Gemini Pro in plaintext mode, and writes per-page UTF-8 Ge'ez
`.txt` plus sidecar metadata `.json` files. Consumed by
`tools/enoch/` and `tools/jubilees/`.

**Scope doc** `JUBILEES.md` covers canonicity, witness coverage,
translation strategy, and the Phase 12 timeline.

**Jubilees scaffold** at `tools/jubilees/multi_witness.py` defines the
Phase 12 witness model (Charles 1895 Ge'ez primary, Dillmann-Rönsch
1874 Ge'ez cross-check, Rönsch 1874 Latin fragments, plus Zone 2
Qumran consult registry).

**DEUTEROCANONICAL.md** Pseudepigrapha section: adds Jubilees row and
documents the shared Ethiopic-pipeline rationale for sequencing
(Enoch first establishes the pipeline; Jubilees reuses it).

## Phase 8c — 1 Enoch pipeline setup (in progress, 2026-04-21)

Pseudepigrapha track — adds a second dedicated pipeline for the Book
of Enoch (Mashafa Henok / መጽሐፈ፡ ሄኖክ), canonical in Ethiopian Orthodox
and quoted in Jude 14-15. Architecturally separate from both the LXX
pipeline and the 2 Esdras Latin pipeline because the primary source
is Ethiopic (Ge'ez) and the OCR backend differs.

- **Source PDFs vendored** in `sources/enoch/` (gitignored; manifest
  with SHA-256 hashes):
  - Charles 1906, *The Ethiopic Version of the Book of Enoch*
    (Anecdota Oxoniensia Semitic Series I.vii) — PD, critical edition
    based on 23 MSS, **our Zone 1 primary**.
  - Dillmann 1851, *Liber Henoch, Aethiopice* — PD, earliest critical
    edition with clean layout (cross-check secondary).
  - Bouriant 1892, *Fragments grecs du livre d'Hénoch* — PD, Codex
    Panopolitanus (chs 1-32 + some 97-107).
  - Flemming & Radermacher 1901, *Das Buch Henoch* (GCS 5) — PD,
    Greek edition with Syncellus fragments and Chester Beatty
    chs 97-107 + German translation.
  - Schodde 1882 English + Charles APOT vol 2 1913 — PD English
    reference.
- **Zone 1 validation oracle (not vendored)**: Beta maṣāḥǝft digital
  Ge'ez TEI XML (`LIT1340EnochE.xml`, Hiob Ludolf Centre, University
  of Hamburg, based on Jerabek 1995). 179,000 Ethiopic characters,
  216 chapter divisions. Mixed CC-BY-SA / NC licensing so not
  redistributed; kept local to the drafter's workspace as a
  cross-check oracle — same pattern as First1KGreek for LXX Swete.
- **OCR pipeline decision**: Azure GPT-5 **fails** on Ge'ez script
  despite handling Greek/Hebrew/Latin reliably. **Gemini 2.5 Flash
  also fails** — it emits Ethiopic characters but hallucinates the
  underlying content. **Gemini 2.5 Pro in plaintext mode succeeds**
  (validated on Dillmann 1851 against the Beta maṣāḥǝft oracle, with
  correct Ethiopic Unicode, word separators, sentence terminators,
  and strong line-level agreement). The Enoch pipeline therefore uses
  Gemini 2.5 Pro; Azure GPT-5 remains primary for LXX + 2 Esdras.
- **Scope doc** at `ENOCH.md`: per-chapter witness coverage,
  compositional structure (Book of Watchers + Parables +
  Astronomical + Dreams + Epistle), canonicity, translation
  strategy, phased timeline.
- **Scaffolding** at `tools/enoch/multi_witness.py` with the target
  interface for per-verse witness aggregation plus Zone 2 consult
  registry (Milik DJD XXXVI for Qumran Aramaic; Nickelsburg
  Hermeneia; Knibb; Black; Isaac in OTP).
- **DEUTEROCANONICAL.md** updated with a new "Pseudepigrapha and
  expanded canon" section covering both 2 Esdras (Phase 10) and
  1 Enoch (Phase 11) with per-work scope docs linked.
- **Translation drafting deferred** until after Phase 9 (LXX
  deuterocanon) and Phase 10 (2 Esdras) complete.

## Phase 8b — 2 Esdras pipeline setup (in progress, 2026-04-21)

Separate-pipeline setup for 2 Esdras (4 Ezra) — which falls outside
the LXX infrastructure because its Greek source is lost and the
text survives only via Latin + 6 daughter translations.

- **Source PDFs vendored** in `sources/2esdras/`:
  - Bensly 1875, *The Missing Fragment of the Latin Translation of
    the Fourth Book of Ezra* (PD, the Amiens Codex 7:36-140 recovery).
  - Bensly (ed. James) 1895, *The Fourth Book of Ezra: The Latin
    Version Edited from the MSS*, in *Texts and Studies III.2* (PD,
    the critical Latin edition — our primary source-of-truth).
  - Violet 1910, *Die Esra-Apokalypse (IV. Esra) I: Die Überlieferung*
    and vol. 2 (GCS 18, PD, parallel-column Latin + Syriac + Ethiopic
    + Arabic + Armenian + Georgian — our multi-witness edition).
- **Scope doc** at `2ESDRAS.md`: per-witness coverage, translation
  strategy (Latin primary with 6 daughter translations as apparatus),
  timeline.
- **Scaffolding** at `tools/2esdras/` with `multi_witness.py` exposing
  the target shape of the per-verse witness aggregator. OCR and
  per-witness transcription pipelines are next.
- **OCR scaffold** at `tools/2esdras/ocr_pipeline.py`:
  - source-aware CLI for `bensly1895`, `bensly1875`,
    `violet1910-vol1`, and `violet1910-vol2`
  - renders local PDF pages via `pdftocairo`
  - calls Azure GPT-5 vision with source-specific transcription
    prompts
  - writes per-page `.txt` plus `.meta.json` provenance sidecars into
    `sources/2esdras/raw_ocr/<source>/`
- **Latin loader scaffold** at `tools/2esdras/latin_bensly.py`:
  - defines the stable `latin/transcribed/chNN.txt` file format
  - exposes `load_chapter()` / `load_verse()` for cleaned Latin input
  - lets `tools/2esdras/multi_witness.py` become partially live as
    soon as Latin chapter files exist, even before daughter witnesses
    are finished
- **Prompts added**:
  - `tools/prompts/transcribe_2esdras_bensly_latin.md`
  - `tools/prompts/transcribe_2esdras_violet_parallel.md`
- **Live OCR runs completed**:
  - Bensly 1895 main-text span (PDF pages 97–178) OCR'd into
    `sources/2esdras/raw_ocr/bensly1895/`
  - Bensly 1875 Missing Fragment span (PDF pages 65–83) OCR'd into
    `sources/2esdras/raw_ocr/bensly1875/`
  - Violet 1910 vol. 1 pilot pages OCR'd into
    `sources/2esdras/raw_ocr/violet1910-vol1/`
- **Intermediate Latin cleanup layers added**:
  - `tools/2esdras/extract_bensly_body.py` now supports both
    `bensly1895` and `bensly1875`
  - body-only working text for the 1895 main text now lives in
    `sources/2esdras/latin/intermediate/bensly1895_body_*`
  - body-only working text for the 1875 Missing Fragment now lives in
    `sources/2esdras/latin/intermediate/bensly1875_body_*`
  - Bensly 1895 chapter-candidate segmentation now lives in
    `sources/2esdras/latin/intermediate/bensly1895_chapter_candidates/`
  - the 1875 Missing Fragment is now verse-indexed as
    `sources/2esdras/latin/intermediate/bensly1875_fragment_verses/ch07_036_105.txt`
  - chapter VII now has a single hybrid working file at
    `sources/2esdras/latin/intermediate/bensly_ch07_hybrid_working.txt`
- **Canonical loader path partially activated**:
  - `sources/2esdras/latin/transcribed/ch07.txt` now carries verses
    36–105 from the Missing Fragment
  - `sources/2esdras/latin/transcribed/ch12.txt` now carries a
    complete explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch02.txt` now carries a partial
    explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch06.txt` now carries a partial
    explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch08.txt` now carries a partial
    explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch09.txt` now carries a partial
    explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch11.txt` now carries a partial
    explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch14.txt` now carries a partial
    explicit-marker publication
  - `sources/2esdras/latin/transcribed/ch16.txt` now carries a partial
    explicit-marker publication
  - `tools/2esdras/publish_explicit_chapter_candidates.py` added so
    additional explicit-marker chapters can be promoted in the same
    conservative way
  - the canonical Latin loader path now spans **all 16 chapters**
  - `tools/2esdras/report_latin_transcribed_coverage.py` now generates
    `sources/2esdras/latin/transcribed/COVERAGE.md` and
    `COVERAGE.json` so the remaining cleanup debt is explicit
  - `tools/2esdras/editorial_cleanup_latin_transcribed.py` applies a
    conservative cleanup pass over the published Latin files
  - `tools/2esdras/check_latin_quality.py` generates
    `sources/2esdras/latin/transcribed/QUALITY_CHECK.md` and
    `QUALITY_CHECK.json`
  - editorial cleanup removed **37 verse-number bleed artifacts** and
    the follow-up pass reduced **digit-bleed and hyphen-break counts to
    zero** across the published Latin files
  - the remaining flagged issues are now explicit in the quality
    report (for example: chapter 10 verse 47 still empty, chapter 12
    contains one surviving ellipsis marker, chapter 16 still carries
    one crop marker)
  - final remaining coverage gaps were completed from the
    **public-domain digital Latin 4 Esdras text** at `vulgate.org`
  - the final QC pass now reports:
    **0 missing-opening gaps, 0 internal gaps, 0 empty verses,
    0 crop markers, 0 ellipsis markers, 0 digit-bleed artifacts,
    0 hyphen-break artifacts**
- **Translation drafting deferred** until Phase 9 (LXX deuterocanon)
  completes. 2 Esdras work is setup/preparation only until then.

## Phase 8 corpus rescue update — 2026-04-21

Follow-up quality work on the deuterocanonical corpus after the first
Phase 8 release.

- **Sirach rescue completed**: the final `low` verses were not true
  paleographic dead ends; they were page-targeting / numbering failures.
  The rescue was corrected to the actual scan pages:
  - `SIR 3:5, 3:7` → vol2 p665
  - `SIR 33:14–16` → vol2 p728
  - `SIR 33:17` → vol2 p734
- **ADE 4:28 corrected from the scan**: direct page recheck showed that
  Swete prints the line **without** `ἐπὶ` before `τράπεζαν Ἁμάν`; the
  verse was promoted from `medium` to `high`.
- **1ES 9 tail block realigned at the source layer**: the residual at
  `1ES 9:35` exposed a broader AI-parse numbering drift in the tail of
  chapter 9. The fix was applied to `parsed_ai/1ES_009.json`, stale
  adjudications for that mis-keyed span were discarded, and the 1ES
  corpus was rebuilt from the corrected source.
- **BAR 1:1 resolved by micro-crop check**: the final breathing-mark
  ambiguity around `Ἀσαδίου / Ἁσαδίου` was resolved by re-fetching the
  page at higher resolution and checking an enlarged crop of the word
  directly. The smooth breathing was legible enough to promote the
  verse to `high`.
- **Residual state after rescue**: **6,337 high**, **0 medium**,
  **0 low** in the current final corpus.
- **Method now documented**: see
  `docs/PHASE8_CORPUS_QUALITY_RESCUE.md` for the repeatable rescue loop
  used to make these improvements.

## Phase 8 corpus milestone — 2026-04-20

LXX deuterocanonical source text ready for Phase 9 drafting. This is
a corpus release, not a translation release — no English verses ship
from Phase 8 itself.

- **Scope**: 13 deuterocanonical books, 6,337 verses total.
- **Transcription**: our own OCR of Swete 1909 (Public Domain) via
  Azure GPT-5 vision, released under CC-BY 4.0.
- **Adjudication**: scan-grounded verdicts against 4 independent
  transcriptions (ours, First1KGreek, Rahlfs-Hanhart, Amicarelli) for
  3,464 verses where our OCR disagreed with at least one witness.
- **Confidence after all rescue passes**: **98.9% high** (3,425), 1.1%
  medium (39), **0% low** — no verses left in an unverified state.
- **Rescue passes** (iteratively):
  1. `rescue_low_conf.py` — 4-source re-adjudication at 3000px scan
     resolution for every initially low/medium verse.
  2. Fixed image-fetch silent-failure bug and a page-metadata bug
     affecting Greek Esther Additions and Tobit chapter 14.
  3. `rescue_hebrew_parallel.py` — 5-source rescue adding Hebrew
     witness (Sefaria Kahana for SIR, Neubauer 1878 for TOB, WLC MT
     parallel for 1ES) to 14 verses in 1ES 5/6/8/9 + SIR 3/40.
  4. `rescue_low_conf_focused.py` — content-based per-verse page
     identification, targeting the final 32 low-conf verses in
     ADE/TOB with a single focused scan per verse. All 32 promoted
     to high with 0 failures.
- **Quality benchmark** (vs First1KGreek as independent validation
  oracle): 72.3% strict agreement, 86.1% functional agreement. 806
  "major" differences verified by the scan adjudicator as legitimate
  Swete (diplomatic Vaticanus) vs First1KGreek (eclectic) textual-
  tradition divergences, not OCR errors. Published in
  `sources/lxx/swete/QUALITY_BENCHMARK.md`.
- **Per-book 100%-high**: WIS, 3MA, 4MA, LJE, ADA. All other books ≥ 97%.
- **Hebrew/MT parallels vendored** (`sources/lxx/hebrew_parallels/`):
  Sefaria Ben Sira (CC0, 1,018/1,019 verses), Sefaria Tobit Neubauer
  1878 (PD, 76/76 verses), 1 Esdras → MT alignment table. Accessible
  via `tools/hebrew_parallels.py::lookup_with_consult`.
- **Yadin 1965 Masada Ben Sira scroll** (Zone 2 consult, per
  REFERENCE_SOURCES.md): a copy of the editio princeps is consulted
  during Sirach drafting. 413 Sirach verses indexed across chs
  4, 39-44, 49, 51 with 100% coverage of the Sir 39:27-44:17 scroll
  range. Consulted via `tools/yadin_masada.py::lookup`; nothing from
  this work appears in COB output or is committed to the repository.
- **Three-zone reference policy** formalized in REFERENCE_SOURCES.md;
  deferred-source integration documented in REVISION_LATER.md.

## v0.2-pauline — 2026-04-18

- Phase: Phase 1 — Pauline epistles
- Verse count: 1925
- Drafter model versions: `gpt-5.4-2026-03-05` × 1390, `gpt-5.4` × 428, `openai/gpt-5.4-20260305` × 107
- Consistency lint: `lint_reports/phase1-pauline.md`
- Deferred contested decisions: ROM.1.1, ROM.1.2, ROM.1.3, ROM.1.4, ROM.1.5, ROM.1.6, ROM.1.7, ROM.1.8, ROM.1.9, ROM.1.11, ROM.1.12, ROM.1.16…

## v0.1-preview-philippians — 2026-04-17

- Phase: Phase 0 — Philippians
- Verse count: 104
- Drafter model versions: `gpt-5.4` × 104
- Consistency lint: `lint_reports/phase0-philippians.md`
- Deferred contested decisions: PHP.1.1, PHP.1.2, PHP.1.6, PHP.1.7, PHP.1.8, PHP.1.9, PHP.1.10, PHP.1.11, PHP.1.13, PHP.1.14, PHP.1.15, PHP.1.16…

## Release plan

- `v0.1-preview-philippians` — Philippians (pilot)
- `v0.2-pauline` — Romans, 1–2 Corinthians, Galatians, Ephesians, Colossians, 1–2 Thessalonians, 1–2 Timothy, Titus, Philemon
- `v0.3-gospels` — Matthew, Mark, Luke, John, Acts
- `v0.4-nt-complete` — General epistles + Revelation
- `v0.5-torah` — Genesis through Deuteronomy
- `v0.6-former-prophets` — Joshua through 2 Kings
- `v0.7-writings` — Psalms, Proverbs, Job, Ruth, Song of Songs, Ecclesiastes, Lamentations, Esther, Daniel, Ezra-Nehemiah, Chronicles
- `v0.8-latter-prophets` — Isaiah, Jeremiah, Ezekiel, the Twelve
- `v1.0-complete` — Full Bible, all phases re-reviewed and re-linted
