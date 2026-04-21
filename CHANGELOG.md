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
  succeeds** (validated on Dillmann 1851 page 15 — correct Ethiopic
  Unicode output with word separators, sentence terminators, and
  Ge'ez numerals preserved). The Enoch OCR pipeline therefore uses
  Gemini 2.5; Azure GPT-5 remains primary for LXX + 2 Esdras.
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
- **Residual state after rescue**: **6,336 high**, **1 medium**,
  **0 low** in the current final corpus.
- **Remaining honest residuals**:
  - `BAR 1:1` — breathing/orthography-level ambiguity still too small to
    promote beyond `medium`
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
