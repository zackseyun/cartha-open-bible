# Changelog

All phase releases are documented here. Individual verse revisions are
tracked in git history on the per-verse YAML files.

## Unreleased

- Repository scaffold
- DOCTRINE.md, METHODOLOGY.md first drafts
- Per-verse YAML schema defined (`schema/verse.schema.json`)

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

