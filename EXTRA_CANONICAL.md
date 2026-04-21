# Extra-canonical scripture in the Cartha Open Bible

This document catalogs the texts outside the 66-book Protestant canon
+ 13 LXX deuterocanonical books that the Cartha Open Bible is
committed to translating and releasing under CC-BY 4.0. It
complements [`DEUTEROCANONICAL.md`](DEUTEROCANONICAL.md) (the 13
LXX-based deuterocanonical books), [`2ESDRAS.md`](2ESDRAS.md) (the
dedicated Latin-primary sub-phase for 2 Esdras), and
[`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md) (the three-zone
scholarly-source policy applied throughout).

> **Status: scope document.** The texts catalogued here are on the
> Cartha Open Bible roadmap. Source acquisition, pipeline build, and
> drafting happen in phases after Phase 9 (LXX deuterocanon). Each
> text gets its own verse-level provenance at release time — we do
> not ship these as vague historical-interest reprints; we translate
> them with the same rigor and transparency as every canonical book
> in COB.

## Why we include these

The Cartha Open Bible's mission is transparent translation of the
biblical textual tradition in its fullest historical form, letting
readers and their faith communities evaluate. That mission does not
end at Protestant or Catholic canon borders. Three concrete
reasons for expanding beyond the deuterocanon:

1. **The New Testament quotes some of these texts explicitly.**
   Jude 14-15 directly quotes 1 Enoch 1:9. Responsible engagement
   with Jude benefits from having a readable, auditable 1 Enoch.

2. **Other Christian traditions receive some of these as canonical.**
   The Ethiopian and Eritrean Orthodox Tewahedo Churches treat 1
   Enoch and Jubilees as Scripture. A Bible that silently excludes
   what these communities confess is a Bible shaped by Western
   printing economics, not by the historical breadth of Christian
   reception.

3. **Early Christian writings shaped the formation of the NT canon
   itself.** The Didache, 1 Clement, and the Shepherd of Hermas
   were included in early NT codices (e.g. Codex Sinaiticus
   includes Hermas; Codex Alexandrinus includes 1 Clement).
   Understanding the process by which the canon formed requires
   access to the texts that were considered alongside the canonical
   books at the time.

## Terminology: "Extra-canonical"

We use "extra-canonical" as a deliberately neutral umbrella:
*extra* meaning *beyond / outside of*, **not** *extra as in
additional Scripture authorized to modify doctrine*. These texts
have varying canonical status across Christian traditions — some
fully canonical (1 Enoch, Jubilees in Ethiopian tradition), some
quasi-canonical historically (2 Esdras in KJV 1611), some never
canonical anywhere (Thunder, Perfect Mind). Every text carries an
explicit canonical-status label at release.

For a scholar-facing label, "pseudepigrapha" is often used for the
Jewish apocalyptic/testamentary works, "Apostolic Fathers" for the
early Christian writings, and "Nag Hammadi library" for the 4th-c.
Coptic codices. Our umbrella term lets one repository house all of
them without forcing a single scholarly-tradition vocabulary on
readers who won't know those conventions.

## Scope

We have three tiers, not by quality but by **reception status** —
which gives a natural labeling order for readers.

### Tier 1 — Extra-canonical with historical canonical status somewhere

These texts have been received as Scripture by at least one
historical Christian tradition (Ethiopian Orthodox, KJV 1611
Apocrypha, Vulgate appendix).

| Text | Original lang | Primary surviving witness | Scope | PD source edition |
|---|---|---|---|---|
| **2 Esdras (4 Ezra)** | Hebrew (lost) → Greek (lost) → Latin | Latin (Bensly 1895) + 6 daughter translations | 16 chapters | See [`2ESDRAS.md`](2ESDRAS.md) |
| **1 Enoch** | Aramaic (fragments at Qumran) → Greek (partial) → Ge'ez | Ethiopic (Charles 1906) | 108 chapters | Charles 1906, Charles 1912, Flemming 1902. **Pipeline setup already in progress as Phase 8c** — see [`ENOCH.md`](ENOCH.md) |
| **Jubilees** | Hebrew (fragments at Qumran) → Greek (fragments) → Ge'ez | Ethiopic (Charles 1895) | 50 chapters | Charles 1895, Charles 1902, Rönsch 1874 (Latin fragments). **Shared Ethiopic pipeline setup now documented** — see [`JUBILEES.md`](JUBILEES.md) |
| **Psalms of Solomon** | Hebrew (lost) → Greek → (Syriac partial) | Greek | 18 psalms | Ryle & James 1891; **Swete vol. III pages 788–810 now fully transcribed** — see [`PSALMS_OF_SOLOMON.md`](PSALMS_OF_SOLOMON.md) |

### Tier 2 — Apostolic Fathers, Jewish apocalyptic, and pseudepigrapha

These texts circulated widely in the early Church and Second Temple
Jewish communities. Some were included in early NT codices
(Sinaiticus, Alexandrinus); none are canonical in any current
Christian canon, but they are uniformly treated as essential
historical-context reading by scholars.

| Text | Original lang | Primary witness | Scope | PD source edition |
|---|---|---|---|---|
| **Didache** (*Teaching of the Twelve Apostles*) | Greek | Codex Hierosolymitanus H54 (Bryennios 1873) | 16 chapters | Hitchcock & Brown 1884; Schaff 1885. See [`DIDACHE.md`](DIDACHE.md) |
| **1 Clement** | Greek | Codex Alexandrinus + H54 | 65 chapters | Lightfoot 1889; Funk 1901. See [`FIRST_CLEMENT.md`](FIRST_CLEMENT.md) |
| **Shepherd of Hermas** | Greek (+ Latin + Ethiopic versions) | Codex Sinaiticus (partial) + Athous | Visions + Mandates + Similitudes | Lightfoot *Apostolic Fathers*; Gebhardt & Harnack 1877 |
| **2 Baruch (Syriac Apocalypse of Baruch)** | Hebrew (lost) → Greek (mostly lost) → Syriac | Syriac (Ceriani 1871) | 87 chapters | Ceriani 1871; Violet 1924 (GCS 32); Charles 1896 |
| **Testaments of the Twelve Patriarchs** | Greek primary; Armenian + Slavonic + Hebrew fragments | Greek | 12 testaments | Charles 1908 critical edition |

### Tier 3 — Early Christian mystical and contemplative texts (Nag Hammadi, with framing)

Three texts from the Nag Hammadi library that are **not explicitly
cosmologically Gnostic**. We include them as 4th-century Christian
mystical/contemplative literature, with clear framing of their
textual date, manuscript situation, and reception history. We **do
not** present them as Scripture in the canonical sense; each is
labeled as historical-context early Christian mystical writing at
release.

| Text | Character | Primary | Secondary |
|---|---|---|---|
| **Gospel of Thomas** | Sayings collection attributed to Jesus, inward-turning and mystical in tone. Not a demiurge cosmology — no evil creator god. Ambiguous theologically; scholars disagree whether to classify it as proto-Gnostic or an independent early Christian wisdom tradition. | Coptic (NHC II.2, 4th c. MS; Greek Vorlage dated 1st-2nd c.) | Greek fragments P.Oxy. 1, 654, 655 (Grenfell & Hunt 1897, 1904 — PD) |
| **Gospel of Truth** | Meditative homily (often attributed to Valentinus), philosophical/contemplative in register. Talks about "ignorance" and "error" in abstract terms. No villainous creator; no full Gnostic cosmology. More a poetic reflection on the Father, the Word, and knowledge than a theological system. | Coptic (NHC I.3 + XII.2) | — |
| **Thunder, Perfect Mind** | Paradoxical divine-feminine monologue ("I am the first and the last; I am the honored one and the scorned one..."). Does not fit any theological system cleanly — not obviously Gnostic, not obviously Jewish wisdom tradition, not obviously Christian. Genuinely uncategorizable. | Coptic (NHC VI.2) | — |

#### What we are NOT including (open to reconsider)

| Text | Reason held out |
|---|---|
| **Apocryphon of John** | Full Yaldabaoth / ignorant-demiurge cosmology explicitly re-casting the Old Testament creator God as a flawed or malevolent figure. Theologically disruptive in a way that the three texts above are not. Open to reconsider if framing can responsibly contextualize it. |
| **Gospel of Philip** | Valentinian sacramental and ontological framework (bridal chamber, five sacraments theology) that would be genuinely theologically disruptive for most Christian readers. Same open-to-reconsider posture. |

## Pipeline groupings

Implementation cost depends on which source-text pipeline a text
reuses. Grouping by pipeline makes the phased plan natural.

### Group A — reuses LXX-style Greek pipeline (Phase 8 infra)

- Didache
- 1 Clement
- Shepherd of Hermas
- Psalms of Solomon (already in Swete vol III; full page span now transcribed)
- Testaments of the Twelve Patriarchs

**Shared infra:** vision OCR of Greek typeset text, 4-source
triangulation against independent transcriptions where they exist,
scan-grounded adjudication against the scan image.
For the non-Swete Group A books, see
[`GREEK_EXTRA_CANONICAL.md`](GREEK_EXTRA_CANONICAL.md) and
`tools/greek_extra_pdf_ocr.py`.

### Group B — reuses 2 Esdras multi-witness pipeline (Phase 8b infra)

- 2 Esdras itself (Phase 10)
- 2 Baruch (Violet 1924 GCS 32 is literally the companion volume to
  Violet 1910; we can lift the same pipeline with minor Syriac
  additions)

### Group C — new Ethiopic (Ge'ez) pipeline

- 1 Enoch
- Jubilees

**What's new:** vision OCR for Ethiopic script (Unicode block
U+1200–U+137F), Ge'ez-specific transcription prompts, Ethiopic
verse-index data model. Both texts amortize the pipeline investment.

### Group D — new Coptic pipeline (with careful license handling)

- Gospel of Thomas
- Gospel of Truth
- Thunder, Perfect Mind

**What's new:** vision OCR for Coptic script (Unicode block
U+2C80–U+2CFF), and case-by-case license research per codex. The
Coptic manuscripts themselves are PD by age (4th c.); the Facsimile
Edition (Robinson 1972-77) has a complicated licensing history
(UNESCO-funded, Egyptian State holdings) that needs per-source
clearance. Where the Facsimile Edition photos are not clean, we
rely on:

- **PD Greek fragments** for Thomas (P.Oxy. 1, 654, 655 — Grenfell
  & Hunt, fully PD)
- **Scholarly consultation** of Layton, Meyer, DeConick critical
  editions as **Zone 2** (reference only, not reproduced)
- **Fresh transcription from cleanly-licensed photographs** where
  we can obtain them — some facsimile page images are available
  under Creative Commons via institutional repositories

For any Tier 3 text where clean primary-source access cannot be
secured under CC-BY-compatible terms, we document the blocker
publicly and translate from what we can legitimately source, with
transparent notes on the source situation per verse.

## Phased rollout

Source-acquisition and pipeline-setup work is already underway in
parallel with Phase 9 prep. Translation drafting for each begins
after Phase 9 (LXX deuterocanon) completes:

| Phase | Texts | Pipeline | Status |
|---|---|---|---|
| **8b** | 2 Esdras — source + pipeline setup | B (Latin + 6 daughters) | ✓ source PDFs vendored, scope doc written, scaffolding in place |
| **8c** | 1 Enoch — source + pipeline setup | C (new Ethiopic pipeline) | ✓ source PDFs vendored, OCR backend selected (Gemini 2.5 Pro plaintext mode; Azure GPT-5 and Gemini Flash fail on Ge'ez), scope doc, scaffolding |
| **8d** | Jubilees — source + shared Ethiopic pipeline setup | C (reuses/shared with Enoch) | ✓ source PDFs vendored, scope doc written, shared `tools/ethiopic/ocr_geez.py` batch CLI in place, scaffolding added |
| **Phase 8e** | Psalms of Solomon — Swete source transcription + scope setup | A (reuses Swete Greek infra) | ✓ full Swete page span transcribed; dedicated scope doc + helper scaffold |
| **8f** | Shared Greek extra-canonical pipeline setup | A (Greek reuse beyond Swete) | ✓ group scope doc + generic local-PDF Greek OCR scaffold + planned source tree |
| **Phase 9** | LXX deuterocanon drafting | Existing LXX infra | Ready to begin |
| **Phase 10** | 2 Esdras drafting | B | Gated on Phase 9 |
| **Phase 11** | 1 Enoch drafting | C | Gated on Phase 9 |
| **Phase 12** | Jubilees drafting | C (reuses Enoch Ethiopic pipeline) | ~2 weeks once C is exercised |
| **Phase 13** | Didache, 1 Clement, Psalms of Solomon drafting | A | 2-3 weeks total |
| **Phase 14** | Shepherd of Hermas, Testaments of the Twelve Patriarchs | A | 3-4 weeks |
| **Phase 15** | 2 Baruch drafting | B (reuses 2 Esdras) | 2 weeks |
| **Phase 16** | Gospel of Thomas, Gospel of Truth, Thunder Perfect Mind | D (new Coptic pipeline + per-codex license research) | 6-8 weeks |

Phases after 10 are parallelizable by pipeline group. Phase 13 is
where we can produce the largest volume of newly-translated
extra-canonical material relative to effort — Greek is what our
stack handles best.

## Labeling and framing principles

Every extra-canonical text released by COB carries the following in
its reader-facing front matter and per-verse provenance:

1. **Plain-language description** of what the text is and when it
   was composed.
2. **Canonical-status table across traditions** — same format as
   the deuterocanonical section. For texts canonical nowhere, this
   is stated explicitly.
3. **Textual-situation summary** — what the primary surviving
   witness is, what was lost, what languages the text passed through.
4. **Reception-history note** — how the early Church, Second Temple
   Jewish communities, or later scholars received it.
5. **For Tier 3 especially: explicit framing** — that the text is
   4th-century Christian mystical/contemplative literature, not
   canonical Scripture in any historical Christian canon, and that
   its inclusion is for historical and theological-literary study,
   not doctrinal formation.

The reader should never be confused about whether a given book is
"Scripture" in the same sense as Romans. Labels are information, not
editorial judgment.

## License handling

Same three-zone policy as every other COB text:

- **Zone 1 (vendored, safe as source):** Pre-1929 public-domain
  source editions (Charles 1895/1902/1906/1912, Bryennios 1883,
  Lightfoot, Bensly 1895, Ceriani 1871, Ryle & James 1891, Grenfell
  & Hunt 1897/1904, Violet 1910/1924, etc.)
- **Zone 2 (consult, not reproduced):** Modern critical editions,
  translations, and commentaries (Ehrman Loeb *Apostolic Fathers*,
  Milik *Books of Enoch*, Charlesworth *OT Pseudepigrapha*,
  Nickelsburg *1 Enoch Hermeneia*, Layton/Meyer/DeConick on Nag
  Hammadi, Robinson *Nag Hammadi Library*, DJD volumes).
- **Zone 3 (forbidden):** modern commercial English translations of
  the Bible or of these specific texts. Not consulted during
  drafting, to prevent derivative-work exposure.

Each per-text translation ships with a per-verse YAML showing Zone 1
sources consulted at drafting time and Zone 2 scholars named at
drafting time (never their specific words).

## Why doing this at all matters

Three things happen when we open this work under CC-BY 4.0:

1. **Every Christian tradition gets a reference point.** An
   Ethiopian Orthodox reader has an open, modern 1 Enoch.
   A scholar teaching patristics has an open, modern Didache.
   A pastor who wants to understand Jude 14-15 doesn't have to
   choose between a Victorian English translation and a copyrighted
   one.

2. **The formation of the canon becomes legible in one library.**
   You can read the Didache next to James, 1 Clement next to
   Hebrews, Psalms of Solomon next to the Psalter, 2 Esdras next
   to Daniel. The historical conversation the canonical authors
   were embedded in becomes visible in a single browsable corpus.

3. **Nothing about this threatens orthodoxy.** Canonical labeling
   is transparent and preserved. Readers know what they are
   reading. Traditions that receive these texts as Scripture
   finally have a free modern version; traditions that don't
   receive them have them as historical context. Neither tradition
   is asked to change; both are served.

That is why this is on the roadmap, and why it is worth doing
carefully.
