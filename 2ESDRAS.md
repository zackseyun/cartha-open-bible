# 2 Esdras (4 Ezra) — scope and source strategy

This document covers the Cartha Open Bible's dedicated sub-phase for
2 Esdras (called 4 Esdras or 4 Ezra in the Vulgate tradition). It
complements [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md) (which covers
the 13 LXX-based deuterocanonical books), [2BARUCH.md](2BARUCH.md)
(the sibling Syriac-primary apocalypse track), and applies the same
three-zone scholarly-source policy defined in
[REFERENCE_SOURCES.md](REFERENCE_SOURCES.md).

> **Status: source-acquisition phase.** The pipeline is architecturally
> distinct from our LXX infrastructure and is being set up fresh.
> Translation drafting will begin after Phase 9 (LXX deuterocanon)
> completes; no English verses from 2 Esdras ship before that.

## Why 2 Esdras needs its own pipeline

The 13 books in [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md) all have
Greek source texts preserved in the Septuagint tradition. Our entire
Phase 8 infrastructure — Swete OCR, 4-source Greek triangulation
(ours / First1KGreek / Rahlfs / Amicarelli), scan-grounded adjudication
against Codex Vaticanus — assumes a Greek source-text layer.

**2 Esdras has no Greek source text.** The textual tradition is:

- **Original Hebrew** (c. 100 CE): lost entirely.
- **Greek translation** (from the Hebrew): lost. Only fragments
  survive (quotations in patristic authors, a handful of papyrus
  scraps).
- **Latin translation** (from the lost Greek): the most complete
  surviving witness. This is what every English translation works
  from as primary.
- **Daughter translations from the same lost Greek**: Syriac,
  Ethiopic, Arabic (two recensions), Armenian, Georgian, Slavonic,
  and Coptic. Each preserves readings the others may have lost.

A responsible 2 Esdras translation therefore:

1. Takes **Latin** as primary source text.
2. Uses **Syriac + Ethiopic + Arabic + Armenian + Georgian** as
   independent witnesses to the lost Greek. Where they disagree with
   the Latin, the disagreement is textually significant and
   footnote-worthy.
3. Does **not** pretend there is a Greek source to reconstruct at
   the word-choice level — the Greek is genuinely lost.

This is not a variant of the LXX pipeline. It is a parallel effort
with its own source acquisition, OCR, and multi-witness adjudication
logic.

## Structure of the book

2 Esdras as printed in the KJV 1611 Apocrypha and modern editions is
a composite text of three independent works:

| Chapters | Name | Origin | Language |
|---|---|---|---|
| 1–2 | **5 Ezra** | Christian addition, 2nd-3rd c. CE | Latin (survives only in Latin) |
| 3–14 | **4 Ezra** (core) | Jewish apocalypse, c. 100 CE | Hebrew original lost; translated via Greek → Latin and other daughter languages |
| 15–16 | **6 Ezra** | Christian addition, 3rd c. CE | Latin (plus fragments of a Greek Vorlage) |

The "core" apocalypse (chs 3–14, the Seven Visions of Ezra) is what
most scholarly attention focuses on. We translate all 16 chapters
as a single work per the traditional English ordering, with the
compositional history noted in the front matter.

## Canonicity

| Tradition | Status |
|---|---|
| Roman Catholic | Appendix to the Vulgate (not canonical but printed with Scripture) |
| Eastern Orthodox (Greek/Russian) | Accepted as 3 Esdras in some Slavonic bibles |
| Ethiopian Orthodox | Canonical |
| Protestant (historic) | Apocrypha (KJV 1611) |
| Jewish tradition | Not in the Hebrew Bible; the Hebrew original was lost in the talmudic era |

Following the Cartha Open Bible policy (see DEUTEROCANONICAL.md),
we take no position on canonicity. We translate and publish with
transparent labeling.

## Source editions — per-witness

### Primary: Latin

The Latin text survives in multiple manuscript families. The
standard critical editions:

| Edition | Year | License | Role for COB |
|---|---|---|---|
| **Bensly, *The Missing Fragment of the Latin Translation of the Fourth Book of Ezra*** | 1875 | Public Domain | Vendored (`sources/2esdras/scans/`). The Amiens Codex fragment — 7:36-140 — restored to the text after being dropped in most medieval MSS. |
| **Bensly (ed. James), *The Fourth Book of Ezra: The Latin Version Edited from the MSS* (Texts & Studies III.2)** | 1895 | Public Domain | Vendored. The full critical Latin edition — our **Zone 1 primary**. |
| **Violet, *Die Esra-Apokalypse (IV. Esra), Erster Teil: Die Überlieferung* (GCS 18)** | 1910 | Public Domain | Vendored. Parallel-column edition of Latin + Syriac + Ethiopic + Arabic + Armenian + Georgian. **Our multi-witness source-of-truth.** |
| **Violet, *Die Apokalypsen des Esra und des Baruch* (GCS 32)** | 1924 | Public Domain | Optional future acquisition — translation-oriented companion volume. |
| **Weber-Gryson, *Biblia Sacra Vulgata* (Stuttgart Vulgate)** | 2007 | Copyright | **Zone 2 consult only.** Critical apparatus informs adjudication; text not reproduced. |
| **Metzger (ed.), *The Fourth Book of Ezra* in *The Old Testament Pseudepigrapha* Vol. 1** | 1983 | Copyright | **Zone 2 consult only.** English translation with introduction. Not tracked word-for-word. |

### Secondary witnesses (daughter translations from the lost Greek)

Vendored via Violet 1910 (parallel columns) and where possible from
independent PD editions:

| Language | PD Edition | Role |
|---|---|---|
| **Syriac** | Ceriani 1868 (*Monumenta Sacra et Profana* vol. V) + Violet 1910 parallel columns | Zone 1 secondary witness |
| **Ethiopic** | Dillmann 1894 (*Veteris Testamenti Aethiopici*) + Laurence 1820 + Violet 1910 | Zone 1 secondary witness |
| **Arabic (two recensions)** | Violet 1910 (from the Vatican + Oxford MSS) | Zone 1 secondary witness |
| **Armenian** | Violet 1910 (from the Mekhitharist editions) | Zone 1 secondary witness |
| **Georgian** | Violet 1910 | Zone 1 secondary witness |
| **Coptic fragments** | Leipoldt, Zeitschrift für die neutestamentliche Wissenschaft 1903 | Optional, small coverage |

All of the above are either directly PD or printed in Violet 1910
which is PD.

### What we do NOT include

- **Slavonic 4 Ezra**: preserved text but textually close to the
  Latin; low incremental value for a translation project and
  not in Violet 1910.
- **Modern reconstructions of the lost Greek** (e.g., Stone's
  speculative retroversions): Zone 2 reference only, never
  reproduced.

## Translation strategy

Adapted from `METHODOLOGY.md` and `REFERENCE_SOURCES.md`:

1. **Latin is the primary source text.** English renderings anchor
   in the Bensly 1895 critical Latin.
2. **Daughter translations provide per-verse textual-critical
   context.** Where Syriac / Ethiopic / Arabic / Armenian / Georgian
   disagree with the Latin in ways that affect meaning, the
   disagreement is flagged in the per-verse YAML and footnoted.
3. **The adjudicator does NOT try to reconstruct the lost Greek.**
   Reconstruction is scholarly speculation and is not the translator's
   job. Witness disagreements are preserved as disagreements.
4. **Three-zone policy applies.** Stuttgart Vulgate and Metzger OTP
   are Zone 2 consult. NIV-family English translations are Zone 3
   forbidden.
5. **Per-verse provenance YAML** follows the same schema as the rest
   of COB, with additional fields for each witness's reading.

## Pipeline components (to be built)

| Component | Status | Purpose |
|---|---|---|
| `sources/2esdras/scans/` | ✓ vendored | PDFs of Bensly 1875, Bensly 1895 (via Texts & Studies v3), Violet 1910 vols 1-2 |
| `sources/2esdras/latin/` | 🔄 in progress | Clean UTF-8 Latin text from Bensly 1895 + 1875 Missing Fragment, per-verse-indexed |
| `sources/2esdras/syriac/`, `/ethiopic/`, `/arabic_armenian/` | ⏳ pending | Clean UTF-8 for each witness, per-verse-indexed |
| `tools/2esdras/ocr_pipeline.py` | ✓ scaffold | Azure GPT-5 vision OCR of local Bensly/Violet PDFs, per-page, with source-specific prompts + `.meta.json` provenance |
| `tools/2esdras/extract_bensly_body.py` | ✓ scaffold | Extracts `[BODY]` from Bensly 1895 / 1875 raw OCR into cleaner Latin working text files for cleanup |
| `tools/2esdras/build_missing_fragment_verses.py` | ✓ scaffold | Builds a verse-indexed working file for the 1875 Missing Fragment (VII 36–105) |
| `tools/2esdras/build_ch07_hybrid.py` | ✓ scaffold | Assembles a chapter VII hybrid working file from 1895 pre/post material plus the 1875 fragment |
| `tools/2esdras/publish_ch07_fragment.py` | ✓ scaffold | Publishes VII 36–105 into `latin/transcribed/ch07.txt`, activating loader coverage for the fragment immediately |
| `tools/2esdras/publish_explicit_chapter_candidates.py` | ✓ scaffold | Conservatively promotes explicit-marker chapter candidates into partial or complete `latin/transcribed/chNN.txt` files |
| `tools/2esdras/editorial_cleanup_latin_transcribed.py` | ✓ scaffold | Conservative editorial cleanup pass for verse-number bleed and obvious split-word artifacts |
| `tools/2esdras/check_latin_quality.py` | ✓ scaffold | Generates a quality report over the current Latin transcribed files |
| `tools/2esdras/supplement_from_vulgate_org.py` | ✓ scaffold | Completes missing verses from the public-domain digital Latin 4 Esdras text while preserving OCR-derived text where present |
| `tools/2esdras/latin_bensly.py` | ✓ active scaffold | Loader for chapter-indexed cleaned Latin (`ch01.txt`, etc.); currently live across all 16 chapters via partial and fragment-backed publications |
| `tools/2esdras/multi_witness.py` | ✓ partial scaffold | Per-verse witness aggregator; Latin path is wired, daughter witnesses still pending |
| `tools/2esdras/build_translation_prompt.py` | ⏳ pending | Phase 10 prompt builder (Latin primary + witnesses + Zone 2) |

## Timeline (indicative)

- **Phase 8b (source acquisition):** this week — vendor PDFs, build OCR pipeline. ≈ 3–4 days. **OCR scaffold now in place.**
- **Phase 8c (transcription):** OCR + hand-verify Latin + primary witnesses. ≈ 1 week. **Bensly 1895 main-text raw OCR (pages 97–178) and Bensly 1875 Missing Fragment raw OCR (pages 65–83) now complete.** The canonical loader path is now live across **all 16 chapters**, with chapter 7 specifically strengthened by the Missing Fragment (36–105). The remaining publication gaps were then completed from the **public-domain digital Latin 4 Esdras text** at `vulgate.org`, with the source URL recorded per chapter header. The final coverage and QC reports now live at:
  - `sources/2esdras/latin/transcribed/COVERAGE.md`
  - `sources/2esdras/latin/transcribed/QUALITY_CHECK.md`
- **Phase 10 (drafting):** after Phase 9 completes — translate ~400 verses across 16 chapters with multi-witness context. ≈ 2 weeks.
- **Phase 10 (revision):** Claude Opus reviser per `REVISION_METHODOLOGY.md`. ≈ 1 week.

Total ≈ 4-5 weeks of focused effort, largely parallelizable against
Phase 9 LXX deuterocanon translation work once source acquisition
completes.

## Why this is worth doing

- **No existing English 2 Esdras is under a clean open license.** NRSV
  and NABRE are copyrighted. Brenton did not include 2 Esdras.
  Bensly's own 1895 English is Victorian in register and limited to
  his critical reconstruction. An open, modern, multi-witness-grounded
  2 Esdras in English is a real contribution.
- **Multi-witness auditability** as our Phase 8 pipeline delivered for
  LXX, applied to 2 Esdras, would give each verse's textual-critical
  footing publicly per verse — which no existing English translation
  of 2 Esdras documents at that granularity.
- **Ethiopian Orthodox readers** have 2 Esdras as canonical but have
  had to use English translations produced for Protestant or Catholic
  audiences. An open translation is a direct service to that
  community.

## Deferred: 1 Enoch

The Book of Enoch (1 Enoch) is structurally similar to 2 Esdras:
Aramaic original lost (except Qumran fragments), Greek translation
partially lost, Ethiopic the only complete witness. It is canonical
in the Ethiopian and Eritrean Orthodox Tewahedo Churches and is
explicitly quoted in Jude 14-15. PD source editions exist (Charles
1906 Ethiopic, Charles 1912 English, Flemming 1902).

**1 Enoch is considered for a future phase after 2 Esdras**, using
a similar Ethiopic-primary + Greek-fragments + Qumran-Aramaic-fragments
(Zone 2 only via Milik 1976) approach. Scope is larger than 2 Esdras
(~108 chapters vs 16), and the Ethiopic-primary OCR pipeline is
different from either LXX or Latin work.

See `ENOCH.md` (to be written) for the full scope document when we
commit to that phase.
