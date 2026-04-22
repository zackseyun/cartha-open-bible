# Jubilees (Mashafa Kufale) — scope and source strategy

This document covers the Cartha Open Bible's dedicated sub-phase for
the Book of Jubilees (Mashafa Kufale / መጽሐፈ፡ ኩፋሌ / "Book of Division").
It sits alongside [ENOCH.md](ENOCH.md) under the shared Ethiopic
pipeline (see [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md)'s
Pseudepigrapha section), and applies the three-zone scholarly-source
policy in [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md).

> **Status: transcription-unblocked phase.** PDFs vendored. Ge'ez OCR
> pipeline is **Gemini 3.1 Pro preview** in plaintext mode. Jubilees
> chapter 1 benchmark is closed (2026-04-22): three independent runs
> were byte-identical and semantically correct against Charles 1902.
> Full-body OCR + chapter mapping are the remaining input-build steps
> before broad translation drafting.

## Why Jubilees

1. **Canonical in the Ethiopian Orthodox Tewahedo Church** — part of
   the 81-book canon (alongside Enoch, Meqabyan, and others). Eritrean
   Orthodox also receives it. No permissively-licensed modern English
   exists for these communities.
2. **Deeply influential on Second Temple Judaism and early
   Christianity.** Jubilees is quoted in the Damascus Document, by
   Tertullian, Syncellus, and indirectly by Epiphanius. Its
   calendrical theology shaped Qumran sectarian thought.
3. **Hebrew original partially recovered at Qumran** (4Q216-228 = the
   Jubilees manuscripts in Hebrew), confirming that Jubilees was
   composed in Hebrew (c. 160-150 BC) and making it an extremely old
   witness to Jewish interpretation of Genesis-Exodus.
4. **Textual situation parallels Enoch.** Hebrew original → Greek
   translation (now largely lost, preserved in citations) → Ethiopic
   (complete, only full witness). Latin fragments survive for
   chapters 13-49 (Rönsch 1874), Syriac citations exist. The
   translation pipeline is nearly identical in structure to Enoch,
   which is why we group them in the same Ethiopic phase.

## Canonicity

| Tradition | Status |
|---|---|
| **Ethiopian Orthodox Tewahedo** | **Canonical** (81-book canon) |
| **Eritrean Orthodox** | **Canonical** |
| **Beta Israel (Ethiopian Jewish)** | Sacred |
| Qumran community | Quoted authoritatively (Damascus Document) |
| Roman Catholic | Not canonical |
| Eastern Orthodox (Greek/Russian) | Not canonical |
| Protestant | Not canonical |

COB policy: no position on canonicity; transparent labeling.

## Compositional overview

Jubilees retells Genesis 1 through Exodus 14 as a revelation to
Moses on Mt. Sinai from the "Angel of the Presence." Its distinctive
feature is the division of history into jubilees (49-year units),
weeks (of years), and years — from creation through the exodus.

50 chapters, ~1,350 verses in Charles's numbering. No compositional
subdivisions like Enoch's 5 books; Jubilees is a single unified
composition.

## Source editions — vendored

### Ethiopic (primary)

| Edition | Year | Role | License |
|---|---|---|---|
| Charles, *The Ethiopic Version of the Hebrew Book of Jubilees* (Oxford, Anecdota Oxoniensia Semitic Series I.viii) | 1895 | **Zone 1 primary** — critical Ethiopic based on 4 MSS (A, B, C, D from Paris/British Museum/Tübingen/Abbadie) with full apparatus | Public Domain |
| Dillmann & Rönsch, *Das Buch der Jubiläen oder die kleine Genesis* (Leipzig) | 1874 | **Zone 1 secondary** — Dillmann's German translation + Rönsch's recovered Latin fragments (chs 13-49) edited critically | Public Domain |

### Latin (secondary witness, chs 13-49)

| Edition | Year | Coverage | License |
|---|---|---|---|
| Rönsch (in Dillmann-Rönsch 1874) | 1874 | ~half the book; independent witness to the lost Greek | Public Domain (Rönsch d. 1888) |

### English reference (not reproduced; verse numbering + cross-check)

| Edition | Year | License |
|---|---|---|
| Charles, *The Book of Jubilees, or The Little Genesis* (London: Black) | 1902 | Public Domain |
| Charles in *Apocrypha and Pseudepigrapha* Vol. 2 | 1913 | Public Domain |

See `sources/jubilees/MANIFEST.md` for SHA-256 hashes and rehydration
commands.

## Zone 2 consult (scholarly, not reproduced)

- **VanderKam, *The Book of Jubilees* (CSCO 510-511, Scriptores
  Aethiopici 87-88, Leuven 1989)** — modern critical Ethiopic edition
  with English translation
- **VanderKam & Milik, *Qumran Cave 4 VIII: Parabiblical Texts Part 1* (DJD XIII, 1994)** — the Qumran Hebrew Jubilees fragments 4Q216-228
- **Segal, *The Book of Jubilees: Rewritten Bible, Redaction, Ideology and Theology* (Brill, 2007)** — modern critical commentary
- **Wintermute, "Jubilees" in OTP vol. 2 (Charlesworth ed.)** (1985) — standard English translation with introduction

## Translation strategy

Same three-zone discipline, adapted for Jubilees:

1. **Primary source**: our own Gemini 3.1 Pro OCR of Charles 1895
   Ge'ez, cross-validated against Dillmann/Rönsch 1874 as a second
   witness. No Beta maṣāḥǝft-style digital Ge'ez oracle exists for
   Jubilees (unlike Enoch), so our OCR cross-check relies on the
   two PD scholarly editions alone.
2. **Secondary textual apparatus** for chapters 13-49: the Latin
   fragments via Rönsch 1874 preserve the earliest textual stratum
   for that material and are shown per-verse alongside the Ethiopic.
3. **Qumran Hebrew fragments**: Zone 2 consult via VanderKam-Milik
   DJD XIII. We footnote fact-level agreements ("4Q219 attests the
   reading here") without reproducing VanderKam's reconstructions.
4. **Per-verse YAML**: standard COB schema with an `enoch_witnesses`
   analog (`jubilees_witnesses`) listing which languages attest each
   verse.

## Pipeline components (planned — shared with Enoch)

The Ethiopic pipeline is built once and used by both Enoch and
Jubilees:

| Component | Purpose | Shared / book-specific |
|---|---|---|
| `tools/ethiopic/ocr_geez.py` | Gemini 3.1 Pro plaintext-mode OCR of Ge'ez scans | **Shared** |
| `tools/ethiopic/run_parallel_ocr.py` | Multi-key / multi-worker batch runner over `ocr_geez.py` | **Shared** |
| `tools/ethiopic/verse_parser.py` | Parse Ge'ez numeral verse markers (፩–፼) | **Shared** |
| `tools/enoch/multi_witness.py` | Enoch-specific witness aggregator | Enoch-specific |
| `tools/jubilees/multi_witness.py` | Jubilees-specific aggregator (Ge'ez + Latin + Zone 2 Qumran Hebrew) | Jubilees-specific |
| `tools/jubilees/detect_chapters.py` | Detect chapter-start pages across Charles 1895 | Jubilees-specific |
| `tools/jubilees/build_page_map.py` | Build/update `sources/jubilees/page_map.json` from detection cache | Jubilees-specific |
| `tools/*/build_translation_prompt.py` | Book-specific translator prompt assembly | Book-specific |

## OCR note — same as Enoch

Critical findings:

- **2026-04-21:** Azure GPT-5 fails on Ge'ez; Gemini 2.5 Flash
  hallucinates; Gemini 2.5 Pro plaintext mode succeeds on Enoch.
- **2026-04-22:** Gemini **3.1 Pro preview** is the regime-shift
  winner for Jubilees: chapter 1 benchmark closed with 100%
  byte-identical 3-run consistency and correct prologue/verse-1
  structure.

Relative costs per page (rough):
- Azure GPT-5: ~2K tokens, FAILS on Ge'ez
- Gemini 2.5 Flash: ~1K tokens, produces Ge'ez but hallucinates content
- Gemini 2.5 Pro plaintext: workable but less stable on Jubilees
- **Gemini 3.1 Pro plaintext**: current production default for Enoch/Jubilees

## Phased timeline

| Phase | Work | Effort | Dependencies |
|---|---|---|---|
| **12a — source acquisition** | ✓ PDFs vendored, MANIFEST written | Done 2026-04-21 | — |
| **12b — transcription** | Gemini 3.1 Pro OCR of Charles 1895 Ethiopic (~180 Ge'ez pages). Build chapter map. Cross-validate against Dillmann-Rönsch 1874 where possible. OCR Rönsch Latin material separately. | In progress | Phase 11 (Enoch) transcription complete — gives us shared tooling |
| **12c — translation** | ~1,350 verses across 50 chapters, multi-witness context, three-zone prompt | 2-3 weeks | 12b complete |
| **12d — revision** | Reviser pass per REVISION_METHODOLOGY.md | 1 week | 12c complete |
| **12e — release** | Tagged release, status.json updated | 1 day | 12d complete |

Total ≈ 4-6 weeks once Phase 11 (Enoch) establishes the shared
Ethiopic tooling. Much of the per-book effort is just running the
shared pipeline against a different book's sources.

## Unique strengths of this translation

- **First CC-BY 4.0 modern English Jubilees.** VanderKam 1989,
  Segal 2007, Wintermute OTP 1985, and Charlesworth collections are
  all copyrighted. Charles 1902 is PD but 123 years old and
  Victorian-register.
- **Ethiopian Orthodox / Eritrean Orthodox readers gain a permissive
  modern English.**
- **Transparent textual provenance per verse** — Ethiopic reading,
  Latin fragment (where applicable, chs 13-49), Qumran Hebrew
  consult (Zone 2), all documented in the per-verse YAML.
- **Shared infrastructure with Enoch** keeps the pipeline lean and
  makes both works benefit from any improvements.

## Future extensions in the Ethiopian broader canon

If and when Jubilees completes successfully, candidates for
further Pseudepigrapha phases remain:

- **Meqabyan 1-3** — Ge'ez-only, Ethiopian Orthodox canonical
- **4 Baruch / Paraleipomena Jeremiou** — Greek + Ge'ez
- **2 Baruch** — Syriac primary

These are not committed to. Each would get its own scope doc if we
pursue it.
