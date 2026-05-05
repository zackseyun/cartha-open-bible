# Source Texts

All source texts the People's Open Bible translates from are vendored in
this directory with their original licenses preserved. The repo's
output (the English translation in `translation/`) is CC-BY 4.0 — but
the upstream sources beneath it carry their own licenses and are
**not** relicensed by including them here.

Each per-verse YAML in `translation/` records which source(s) it drew
from via the `edition` enum on its `source` block (see
`schema/verse.schema.json`).

## Layout at a glance

```text
sources/
├── README.md                          ← this file
│
├── nt/                                Greek New Testament
│   └── sblgnt/
├── ot/                                Hebrew Bible (Protestant OT)
│   ├── wlc/                            Westminster Leningrad Codex via OSHB
│   └── uwhb/                           unfoldingWord Hebrew Bible
│
├── lxx/                               Septuagint + LXX-adjacent corpora
│   ├── swete/                          Swete 1909–1930 (PD; primary LXX)
│   ├── rahlfs/                         Rahlfs 1935 — Zone 2 consult only
│   ├── psalms_of_solomon/              dedicated extra-canonical track
│   ├── psalm_151/                      Greek Psalm 151
│   ├── prayer_of_manasseh/             Charles APOT 1913 (PD)
│   └── hebrew_parallels/               Hebrew/Aramaic Vorlage tables
│
├── hebrew_sirach/                     Hebrew Ben Sira witness layer
│   ├── schechter_1899/                 Schechter & Taylor 1899 (PD)
│   ├── genizah_photos/                 fresh AI-vision transcription work
│   └── masada/                         status notes (license-restricted MS)
│
├── aramaic_tobit/qumran/              4Q196–4Q200 status notes
│
├── greek_extra/                       group-A pipeline landing zone
├── 1_clement/                         Lightfoot 1889, Funk 1901 (PD)
├── didache/                           Hitchcock & Brown 1884, Schaff 1885 (PD)
├── shepherd_of_hermas/                Lightfoot 1891 (PD)
├── testaments_twelve_patriarchs/      Charles 1908 Greek + Sinker 1879 (PD)
│
├── enoch/                             1 Enoch (Geʿez primary)
├── jubilees/                          Mashafa Kufale (Geʿez primary)
├── 2baruch/                           Syriac Apocalypse of Baruch
├── 2esdras/                           4 Ezra (Latin primary, 6 daughter
│                                      versions for textual control)
├── nag_hammadi/                       Coptic — Thomas, Truth, Thunder
│
└── references/                        per-chapter scholarly orientation
                                       JSONs (Sirach 24, Prayer of
                                       Manasseh)
```

The repo also has a repo-root [`REFERENCE_SOURCES.md`](../REFERENCE_SOURCES.md)
that defines a three-zone policy for *consultation-only* references
(scholarly editions, restricted-license MS photos) used during
adjudication but never reproduced. Anything in this directory is **Zone
1** — vendored, safe to redistribute, and used as actual translation
input.

## Vendored sources — canonical Old & New Testament

### SBLGNT — Greek New Testament + morphological parsing
- **Directory:** `nt/sblgnt/`
- **Source repo:** https://github.com/morphgnt/sblgnt
- **Editor (text):** Michael W. Holmes
- **Editor (morphology):** James K. Tauber
- **Publisher:** Society of Biblical Literature / Logos Bible Software
- **Date:** 2010 (text), ongoing (morphology)
- **License — Greek text:** SBLGNT End User License Agreement
  (http://sblgnt.com/license/). Permits free personal and commercial
  use, quotation up to 1,000 verses per work with attribution,
  translation into other languages, and distribution in electronic
  products subject to attribution requirements.
- **License — morphological parsing:** Creative Commons
  Attribution-ShareAlike 3.0 (CC-BY-SA 3.0). See
  `nt/sblgnt/LICENSE.md`.
- **Required attribution:**
  > Scripture quotations marked SBLGNT are from the SBL Greek New Testament.
  > Copyright © 2010 Society of Biblical Literature and Logos Bible Software.

### Westminster Leningrad Codex (WLC) — via Open Scriptures Hebrew Bible
- **Directory:** `ot/wlc/`
- **Source repo:** https://github.com/openscriptures/morphhb (OSHB)
- **Underlying text:** Transcription of the Leningrad Codex B19A
  (1008 AD), the oldest complete Hebrew Bible manuscript. The
  underlying WLC text is in the public domain.
- **License — this distribution:** CC-BY 4.0. See `ot/wlc/LICENSE.md`.
- **Required attribution:**
  > Original work of the Open Scriptures Hebrew Bible available at
  > https://github.com/openscriptures/morphhb

### unfoldingWord Hebrew Bible (UHB)
- **Directory:** `ot/uwhb/`
- **Source repo:** https://git.door43.org/unfoldingWord/hbo_uhb
- **License:** CC-BY-SA 4.0. See `ot/uwhb/LICENSE.md`.
- **Trademark note:** "unfoldingWord" is a registered trademark.
  Redistribution in modified form requires removing the trademark.
- **Required attribution:**
  > The original work by unfoldingWord is available from
  > https://www.unfoldingword.org/uhb

## Vendored sources — Septuagint and LXX-adjacent

### Swete LXX (1909–1930) — primary LXX witness
- **Directory:** `lxx/swete/`
- **Edition:** Henry Barclay Swete, *The Old Testament in Greek
  according to the Septuagint*, Cambridge University Press, vols.
  I–III.
- **Status:** Public domain (Swete d. 1917; volumes pre-1929).
- **Why Swete and not Rahlfs:** every available digital Rahlfs is
  CC-BY-NC, NC-derived, or otherwise restrictive. Swete is fully PD,
  was OCR'd in-house, and covers every deuterocanonical book we need.
  See `lxx/swete/README.md` for the full rationale.
- **Our work:** OCR + cleaned UTF-8 transcription is our own,
  released as part of the POB output corpus under CC-BY 4.0.

### Rahlfs LXX (1935) — not vendored
- **Directory:** `lxx/rahlfs/`
- **Status:** **NOT vendored.** No CC-BY-compatible Rahlfs
  digitization exists. The directory is intentionally empty of source
  text. See `lxx/rahlfs/README.md` for the rationale and
  [`../REFERENCE_SOURCES.md`](../REFERENCE_SOURCES.md) for the policy
  governing Zone 2 references.

### Psalms of Solomon — dedicated track
- **Directory:** `lxx/psalms_of_solomon/`
- **Source:** within the Swete vol. III corpus (pp. 765–787 area).
- **Status:** PD. Drafted as its own extra-canonical book in POB.

### Psalm 151
- **Directory:** `lxx/psalm_151/`
- **Source:** Swete LXX + a local Hebrew consult enhancement layer.
- **Status:** PD.

### Prayer of Manasseh
- **Directory:** `lxx/prayer_of_manasseh/`
- **Source:** R. H. Charles (ed.), *The Apocrypha and Pseudepigrapha
  of the Old Testament*, Vol. 1 (Oxford: Clarendon Press, 1913), pp.
  636–640. Not in Codex Vaticanus, so Swete does not cover it.
- **Status:** PD (Charles d. 1931; volume pre-1929).
- **Output:** 15-verse cleaned Greek corpus at `corpus/MAN.jsonl`.

### Hebrew parallels for the LXX deuterocanon
- **Directory:** `lxx/hebrew_parallels/`
- **Purpose:** clean-licensed Hebrew/Aramaic witnesses that predate
  the Greek and serve as *Vorlage* (translation base) where the
  scholarly consensus is that the Hebrew is genuine.
- **Notable contents:**
  - `sefaria_ben_sira.json` — Sirach Hebrew, CC0 (Sefaria / Kahana edition).
- **License:** mixed; each file is documented in the directory
  README. Zone-2 references (Fitzmyer DJD XIX, Beentjes,
  Skehan/Di Lella, Göttingen) are consulted via `tools/hebrew_parallels.py`
  but never vendored.

## Vendored sources — Hebrew Sirach witness layer

### Schechter & Taylor 1899
- **Directory:** `hebrew_sirach/schechter_1899/`
- **Edition:** Solomon Schechter & Charles Taylor, *The Wisdom of Ben
  Sira: Portions of the Book Ecclesiasticus from Hebrew Manuscripts in
  the Cairo Genizah Collection*, Cambridge University Press, 1899.
- **Status:** PD (Schechter d. 1915, Taylor d. 1908). Covers MSS A & B.
- **Vendored:** full PDF (`schechter_1899.pdf`).

### Genizah photo transcription work
- **Directory:** `hebrew_sirach/genizah_photos/`
- **Sources:** Cambridge Digital Library and other public-domain
  photograph collections of additional Genizah folios (MSS C, D, E, F,
  extra B). License terms vary per item; only items with
  research+redistribution-safe terms are processed here.
- **Output:** fresh AI-vision Hebrew transcription, released under
  CC-BY 4.0 as part of POB output.

### Masada Ben Sira scroll
- **Directory:** `hebrew_sirach/masada/`
- **Status:** **No vendored text.** The high-resolution photographs
  of Mas1h are held under restrictive license terms incompatible with
  CC-BY redistribution. For Sirach 39:27–43:30 we currently fall back
  to Swete + Genizah MS B. See the directory README for the
  upgrade-when-licensable plan.

## Vendored sources — Aramaic Tobit

### Qumran Tobit fragments (4Q196–4Q200)
- **Directory:** `aramaic_tobit/qumran/`
- **Status:** **No vendored text.** Surviving photographs are
  license-restricted. Working Tobit source is Swete LXX (Long
  Recension / Codex Sinaiticus), the same base used by NRSV, NABRE,
  and Orthodox Study Bible. Fragmentary Aramaic/Hebrew readings are
  consulted via published apparatus only (Zone 2). When licensable
  facsimile access becomes available, the Tobit verse YAMLs will be
  upgraded in place with a documented re-translation pass.

## Vendored sources — Greek extra-canonical (Group A)

These four texts are Greek-primary and share an OCR pipeline
(`tools/greek_extra_pdf_ocr.py`). All vendored editions are public
domain. The shared landing zone is `greek_extra/`; each book also has
its own top-level directory with `MANIFEST.md` (SHA-256 hashes for
rehydration) and `scans/` (gitignored).

### 1 Clement
- **Directory:** `1_clement/`
- **Vendored:** Lightfoot 1889 (*The Apostolic Fathers*), Funk 1901
  (*Patres Apostolici*).

### Didache
- **Directory:** `didache/`
- **Vendored:** Hitchcock & Brown 1884, Schaff 1885 (*The Oldest
  Church Manual*).

### Shepherd of Hermas
- **Directory:** `shepherd_of_hermas/`
- **Vendored:** Lightfoot 1891 (*The Apostolic Fathers*, 2nd part).

### Testaments of the Twelve Patriarchs
- **Directory:** `testaments_twelve_patriarchs/`
- **Vendored:** Charles 1908 Greek edition (`charles_1908_greek_versions.pdf`)
  as the primary drafting witness, Sinker 1879 (collation/apparatus
  appendix), Charles 1908 English (`charles_1908_testaments.pdf`) as
  numbering reference.

## Vendored sources — Geʿez-primary pseudepigrapha

### 1 Enoch
- **Directory:** `enoch/`
- **Primary witness:** Geʿez (only complete witness).
- **Vendored editions (all PD):**
  - Charles 1906 — *The Ethiopic Version of the Book of Enoch*
  - Dillmann 1851 — *Liber Henoch, Aethiopice*
  - Bouriant 1892 — Greek fragments (Codex Panopolitanus)
  - Flemming 1901 — Greek + German (GCS 5)
  - Schodde 1882 — English reference
  - Charles APOT vol. 2 1913 — revised English reference
- **OCR:** Gemini 3.1 Pro Geʿez OCR; Azure GPT-5 second-pass for the
  Greek fragments.
- **Scope doc:** [`../ENOCH.md`](../ENOCH.md).
- **Manifest:** SHA-256 hashes in `enoch/MANIFEST.md`.

### Jubilees (Mashafa Kufale)
- **Directory:** `jubilees/`
- **Primary witness:** Geʿez (only complete witness).
- **Vendored editions (all PD):**
  - Charles 1895 — Geʿez critical edition
  - Charles 1902 — English reference
  - Dillmann/Rönsch 1874 — composite Latin fragments (chs 13–49)
- **OCR:** Gemini 3.1 Pro for Geʿez.
- **Zone 2:** Qumran Hebrew (4Q216–228) consulted via VanderKam-Milik
  apparatus, never reproduced.
- **Scope doc:** [`../JUBILEES.md`](../JUBILEES.md).

## Vendored sources — Syriac- and Latin-primary apocalypses

### 2 Baruch (Syriac Apocalypse of Baruch)
- **Directory:** `2baruch/`
- **Primary witness:** Syriac (the only complete witness; lost Hebrew
  → lost Greek → surviving Syriac).
- **Vendored editions (all PD):**
  - Ceriani 1871 — *Apocalypsis Baruch syriace* in *Monumenta sacra
    et profana* 5.2 (primary Syriac base text)
  - Kmosko 1907 — *Patrologia Syriaca* 1.2 (secondary)
  - Violet 1924 — GCS 32 orientation/structure witness
  - Charles 1896 — English numbering/orientation only
- **Scope doc:** [`../2BARUCH.md`](../2BARUCH.md).
- **Manifest:** SHA-256 hashes in `2baruch/MANIFEST.md`.

### 2 Esdras (4 Ezra)
- **Directory:** `2esdras/`
- **Primary witness:** Latin (with six daughter versions used as
  independent textual controls: Syriac, Ethiopic, Arabic, Armenian,
  Georgian, Coptic fragments).
- **Vendored editions (all PD):**
  - Violet 1910 vols. 1–2 — *Die Esra-Apokalypse* (GCS 18), parallel
    columns of Latin + Syriac + Ethiopic + Arabic + Armenian + Georgian
  - Bensly 1875 — *The Missing Fragment of the Latin Translation of
    the Fourth Book of Ezra* (the Amiens Codex restoration of 7:36–140)
  - *Texts and Studies* III (1895) — contains Bensly/James, the Latin
    critical edition
- **Scope doc:** [`../2ESDRAS.md`](../2ESDRAS.md).

## Vendored sources — Coptic Nag Hammadi gospels

### Gospel of Thomas, Gospel of Truth, Thunder, Perfect Mind
- **Directory:** `nag_hammadi/`
- **Primary witnesses:** Sahidic Coptic from the Nag Hammadi codices,
  fetched as TEI XML from the Coptic Scriptorium project (Brill
  Facsimile Edition Codex II/III/VI scans, born-digital editions).
- **License:** CC-BY 4.0 (Coptic Scriptorium). Greek overlap fragments
  for Thomas (P.Oxy. 1, 654, 655) are consulted via published witnesses.
- **Required attribution:** Dilley 2025 + Coptic Scriptorium per the
  per-text `manifest.json` in `nag_hammadi/texts/<book>/`.
- **Scope doc:** [`../docs/phase-e-nag-hammadi.md`](../docs/phase-e-nag-hammadi.md).

## How sources are used

The People's Open Bible translates from the **most-original extant text**
for each book, not uniformly from one edition. The current per-book
mapping:

| Corpus | Primary witness | Secondary witnesses |
|---|---|---|
| Protestant NT | SBLGNT | morphology (reference only) |
| Protestant OT | WLC | UHB (where OSHB updates apply) |
| Deuterocanon composed in Greek (Wisdom, 2 Maccabees, Greek additions to Esther + Daniel) | Swete LXX | — |
| Deuterocanon where Hebrew/Aramaic original is lost (1 Maccabees, Judith, Baruch + Letter of Jeremiah, 1 Esdras, 3–4 Maccabees) | Swete LXX | — |
| Tobit | Swete LXX (Long Recension / Sinaiticus) | Qumran 4Q196–4Q200 (Zone 2 consult) |
| Sirach | Hebrew Genizah where extant (Schechter + fresh AI transcription) | Swete LXX where Hebrew is lost; Hebrew parallels table |
| Psalms of Solomon | Swete LXX | — |
| Psalm 151 | Swete LXX | local Hebrew consult |
| Prayer of Manasseh | Charles APOT 1913 | — |
| 1 Enoch | Geʿez (Charles 1906 + Dillmann 1851) | Greek fragments (Bouriant, Flemming); Qumran Aramaic via Zone 2 |
| Jubilees | Geʿez (Charles 1895) | Latin (Rönsch 1874, chs 13–49); Qumran Hebrew via Zone 2 |
| 2 Baruch | Syriac (Ceriani 1871) | Kmosko 1907; Violet 1924 |
| 2 Esdras (4 Ezra) | Latin (Bensly + Violet) | six daughter versions |
| Didache, 1 Clement, Shepherd of Hermas, Testaments of the Twelve Patriarchs | Greek (Lightfoot, Funk, Charles 1908, etc.) | — |
| Nag Hammadi (Thomas, Truth, Thunder) | Sahidic Coptic (Coptic Scriptorium) | Greek Oxyrhynchus fragments for Thomas |
| Cross-reference for NT OT-quotations | Swete LXX | — |

For deuterocanon specifically, the per-book source-acquisition matrix
and the integrity commitments live in [`../DEUTEROCANONICAL.md`](../DEUTEROCANONICAL.md).
For pseudepigrapha and other extra-canonical books, see the per-book
scope docs at the repo root (`ENOCH.md`, `JUBILEES.md`, `2BARUCH.md`,
`2ESDRAS.md`, `DIDACHE.md`, `FIRST_CLEMENT.md`,
`GREEK_EXTRA_CANONICAL.md`, `PRAYER_OF_MANASSEH.md`,
`PSALMS_OF_SOLOMON.md`, `EXTRA_CANONICAL.md`,
`APOCRYPHA_PROVENANCE.md`).

## License scope — important note

The People's Open Bible's output (the English translation in
`translation/`) is released under **CC-BY 4.0** (see root `LICENSE`).

**Source texts vendored in this directory retain their own licenses
and are not relicensed by inclusion here.** Anyone reusing content
from this directory must comply with the individual source's license:

| Source | License | Reuse constraint |
|---|---|---|
| SBLGNT text | SBLGNT EULA | Attribution + quotation limits |
| SBLGNT morphology | CC-BY-SA 3.0 | Share-alike on derivatives |
| WLC (via OSHB) | CC-BY 4.0 | Attribution |
| UHB | CC-BY-SA 4.0 | Attribution + share-alike + trademark restrictions |
| Swete LXX (raw scans + our OCR) | Public Domain (scans); CC-BY 4.0 (our OCR/transcription) | Attribution to POB for the OCR layer |
| Schechter & Taylor 1899 | Public Domain | None |
| Charles 1895 / 1902 / 1906 / 1908 / 1913, Dillmann 1851, Bouriant 1892, Flemming 1901, Lightfoot 1889/1891, Funk 1901, Hitchcock & Brown 1884, Schaff 1885, Sinker 1879, Ceriani 1871, Kmosko 1907, Violet 1910/1924, Bensly 1875, Schodde 1882, Rönsch 1874 | Public Domain (pre-1929 / author d. before 1954) | None |
| Sefaria Ben Sira | CC0 | None |
| Coptic Scriptorium TEI (Nag Hammadi) | CC-BY 4.0 | Attribution (Dilley 2025 + Coptic Scriptorium) |

The People's Open Bible's English output is a new creative work,
licensed independently (CC-BY 4.0). The share-alike clauses on the
SBLGNT morphology and the UHB do **not** propagate to our translation
output, which is not a share-alike derivative of those works.

If you build on the People's Open Bible *and* incorporate any of the
vendored source data, you must comply with the source license for that
data separately.

## Vendoring procedure

Source texts are vendored (copied in) rather than referenced as git
submodules. Rationale:
- Full auditability — anyone cloning has everything they need to
  verify the translation without separate network fetches.
- Stability — upstream repos can disappear or change.
- Reproducibility — `tools/verify.py` and `tools/build_status.py`
  depend on exact byte-level source text.

Large PDFs (Geʿez Charles, Ceriani Syriac, Violet GCS volumes, etc.)
are **not** committed directly. Each book directory carries a
`MANIFEST.md` that records the expected file paths, sizes, SHA-256
hashes, and Internet Archive identifiers so a fresh checkout can
re-download and verify byte-for-byte equivalence.

To update a source to a newer version, the update is itself a git
commit with a clear message documenting what changed and why.

## See also

- [`../METHODOLOGY.md`](../METHODOLOGY.md) — drafting pipeline
- [`../DOCTRINE.md`](../DOCTRINE.md) — translation principles
- [`../REFERENCE_SOURCES.md`](../REFERENCE_SOURCES.md) — three-zone
  consultation policy for non-vendored references
- [`../DEUTEROCANONICAL.md`](../DEUTEROCANONICAL.md) — per-book
  deuterocanon source matrix
- [`../EXTRA_CANONICAL.md`](../EXTRA_CANONICAL.md) — extra-canonical
  scope and inclusion criteria
