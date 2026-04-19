# The Deuterocanonical Books in the Cartha Open Bible

This document explains why the Cartha Open Bible includes the
Deuterocanonical books (also called the Apocrypha, or
*Anagignoskomena*), how we intend to translate them, and what
commitments we make about their integrity and presentation. It
complements [DOCTRINE.md](DOCTRINE.md) (theological stance),
[METHODOLOGY.md](METHODOLOGY.md) (pipeline), and
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md) (revision process).

> **Status: first draft, strategy phase.** Translation work for these
> books has not yet begun. This document is published first so the
> approach can be scrutinized before any verse is drafted.

## Why include these books

The Cartha Open Bible exists to make the biblical textual tradition
transparent and auditable. Excluding these books would itself be a
theological editorial decision — one that curates which texts readers
are permitted to evaluate. COB's mission is the opposite: present the
tradition; let the reader and their faith community judge.

Concretely:

- **Historical precedent.** Luther's 1534 German Bible included the
  Apocrypha in a clearly labeled section between the Testaments,
  calling them "books not regarded as equal to the Holy Scriptures,
  yet useful and good to read." The 1611 King James Version likewise
  included them as a middle section. Their removal from most Protestant
  Bibles is a 19th-century development driven primarily by printing
  economics at the British and Foreign Bible Society, not theological
  consensus.
- **Ecumenical reach.** Roman Catholic (Trent, 1546), Eastern Orthodox
  (Synod of Jerusalem, 1672), and Oriental Orthodox canons include
  these books as fully canonical. Excluding them makes COB useful only
  to a subset of Christian readers. Including them, clearly labeled,
  serves the whole church without pronouncing on canonicity.
- **Intertestamental witness.** These books describe the world Jesus
  was born into — the Hasmonean revolt (1-2 Maccabees), Second Temple
  wisdom traditions (Sirach, Wisdom of Solomon), and Jewish devotional
  life in the diaspora (Tobit, Judith). Reading the NT without them
  means reading a text whose cultural assumptions are partially
  invisible.
- **Consistency with COB's stated philosophy.** DOCTRINE.md commits
  to "preserve theological tension rather than resolve it" and
  "original-language primacy over translation tradition." Including
  texts that are canonical in some traditions and not in others
  preserves the tension; excluding them resolves it in one direction.

We do not pronounce on canonicity. We translate and publish.

## Our theological stance on canonicity

COB takes no position on whether these books are canonical. This
refusal is itself a stance, and we name it clearly:

- **To Protestant readers:** including these books does not assert
  they carry the same authority as the Protestant canon. Article 6
  of the Anglican Articles of Religion names them as books the church
  "doth read for example of life and instruction of manners, but yet
  doth it not apply them to establish any doctrine." That is a
  reasonable stance for any reader to take while using this edition.
- **To Catholic and Orthodox readers:** including these books respects
  the canonical status your traditions have affirmed since antiquity.
  We translate them with the same rigor and per-verse provenance as
  the Protestant canon.
- **To all readers:** each book is labeled with its canonical status
  across the major traditions, so no reader encounters a book without
  knowing which Christian communities receive it and how.

This is the same posture DOCTRINE.md takes toward contested theological
terms: name the controversy, present the alternatives, let the reader
judge.

## Terminology

Different Christian traditions use different names for this corpus.
None of the terms is theologically neutral. We use them as follows:

| Term | Tradition | Meaning |
|---|---|---|
| **Apocrypha** | Protestant | "hidden things" — sometimes pejorative |
| **Deuterocanonical** | Catholic | "of the second canon" — included but later affirmed |
| **Anagignoskomena** | Orthodox | "worthy to be read" |
| **Intertestamental books** | neutral-academic | descriptive, narrow |

In COB we use **Deuterocanonical** as our primary term in filenames
and repository documentation because it is the most widely
understood non-pejorative option in contemporary scholarship. In
user-facing contexts (the mobile app, published editions) we will
label the section as **"Deuterocanonical Books (Apocrypha)"** so
readers from every tradition recognize what they are reading.

## Scope — which books, from which sources

### Books included

Our target scope is the complete corpus recognized by at least one
major Christian tradition with a stable textual history:

| Book | Catholic | Orthodox | Protestant (historic) | Primary source |
|---|---|---|---|---|
| Tobit | ✓ | ✓ | Apocrypha | LXX |
| Judith | ✓ | ✓ | Apocrypha | LXX |
| Greek Additions to Esther | ✓ | ✓ | Apocrypha | LXX |
| Wisdom of Solomon | ✓ | ✓ | Apocrypha | LXX |
| Sirach (Ecclesiasticus) | ✓ | ✓ | Apocrypha | LXX |
| Baruch (incl. Letter of Jeremiah) | ✓ | ✓ | Apocrypha | LXX |
| Additions to Daniel (Pr Azariah, Song of Three, Susanna, Bel) | ✓ | ✓ | Apocrypha | LXX |
| 1 Maccabees | ✓ | ✓ | Apocrypha | LXX |
| 2 Maccabees | ✓ | ✓ | Apocrypha | LXX |
| 1 Esdras | appendix | ✓ | Apocrypha | LXX |
| Prayer of Manasseh | appendix | ✓ | Apocrypha | LXX |
| Psalm 151 | — | ✓ | — | LXX |
| 3 Maccabees | — | ✓ | — | LXX |
| 4 Maccabees | — | appendix | — | LXX |

**2 Esdras (4 Ezra)** is deferred. Its main body survives only in
Latin (from a lost Greek translation of a lost Hebrew/Aramaic
original) and a handful of Eastern-language witnesses (Syriac,
Ethiopic, Armenian, Georgian). Including it responsibly requires a
separate source-acquisition phase for the Latin text and a different
textual apparatus than the LXX-based books. We will revisit after
Phase 1 ships.

### Source editions — per-book, most-original extant text

We translate each book from the **most-original surviving text we can
lawfully access**, not uniformly from one edition. This is more
faithful to the composition history of these books — and for 12 of
14 books, the Greek LXX *is* the original or the sole surviving
witness, so LXX is the right answer on textual grounds, not as a
compromise.

Field research (2026-04-18) confirmed that the commonly-referenced
**Rahlfs LXX 1935** has no CC-BY-compatible digital transcription
we can vendor: every digital Rahlfs edition we evaluated is either
CC-BY-NC-SA (eliranwong, CenterBLC), CC-BY-SA (Perseus, First1KGreek
derivatives), or restrictive (CCAT). STEPBible's announced TAGOT
has not shipped.

Instead, our LXX source is **Henry Barclay Swete, *The Old Testament
in Greek According to the Septuagint*, 3 vols. (Cambridge University
Press, 1909–1930)** — fully public domain (Swete died 1917) and
hosted as scanned PDFs on Internet Archive. Swete's edition contains
every deuterocanonical book we need. We transcribe the Greek
ourselves from the archival page scans using AI vision, releasing
the transcription under CC-BY 4.0. This is legally clean (PD source
+ our own work) and produces a working source text whose provenance
is auditable to specific public-domain page images.

For the two books where a non-Greek original survives (Sirach in
Hebrew, Tobit in Aramaic), we translate primarily from the original
language where we can lawfully access photographs, consulting the
Greek where the original is lost or damaged.

#### Per-book source path

| Book | Original language | Primary source for COB | Status |
|---|---|---|---|
| Wisdom of Solomon | Greek (original) | Swete LXX vol. II (PD) | ✓ path clear |
| 2 Maccabees | Greek (original) | Swete LXX vol. III (PD) | ✓ path clear |
| Greek Additions to Esther | Greek (original) | Swete LXX vol. II (PD) | ✓ path clear |
| Greek Additions to Daniel | Greek (original) | Swete LXX vol. III (PD) | ✓ path clear |
| 1 Maccabees | Hebrew (lost) | Swete LXX vol. III (PD) | ✓ path clear |
| Judith | Hebrew (lost) | Swete LXX vol. II (PD) | ✓ path clear |
| Baruch + Letter of Jeremiah | Hebrew (lost) | Swete LXX vol. III (PD) | ✓ path clear |
| 1 Esdras | Greek (Semitic Vorlage lost) | Swete LXX vol. II (PD) | ✓ path clear |
| Prayer of Manasseh | Greek | Swete LXX vol. III (PD) | ✓ path clear |
| Psalm 151 | Hebrew (partial at 11QPsa) | Swete LXX; Hebrew: acquisition in progress | ⚠ Hebrew fragment blocked on licensing |
| 3 Maccabees | Greek | Swete LXX vol. III (PD) | ✓ path clear |
| 4 Maccabees | Greek | Swete LXX vol. III (PD) | ✓ path clear |
| **Sirach** | **Hebrew** | Hebrew: Schechter 1899 (PD, MSS A & B); fresh vision transcription from PD photos for MSS C–F; LXX (Swete) where Hebrew is lost | ✓ MSS A & B covered; MSS C–F via PD re-publications and fresh transcription |
| **Tobit** | **Aramaic** | LXX (Swete) primary; Aramaic Qumran fragments to be added when available | ⚠ Aramaic originals held under restrictive license |

Legend: ✓ = clean path, material in hand or freely acquirable. ⚠ = partial block, documented workaround in place.

**Masada Ben Sira scroll** (Mas1h) covers Sirach 39:27–43:30 and is
the only pre-medieval Hebrew Sirach witness. Its surviving
photographs are held under restrictive license terms; until direct
access is available, we translate that passage from the Greek (Swete)
and note transparently in the front-matter that the pre-medieval
Hebrew witness is not in our current source pipeline.

**Qumran Tobit fragments** (4Q196–4Q200) are the sole Aramaic/Hebrew
witness to Tobit and cover approximately 20% of the book. Same
licensing situation, same interim posture: LXX Greek primary with
transparent notation.

Scholarly editions (Beentjes 1997, Skehan & Di Lella 1987, Fitzmyer
1995 DJD XIX, etc.) are cited in footnotes for factual textual-critical
claims — which are not copyrightable — but not reproduced.

## Source acquisition status

The following table tracks every source of interest and its current
state in the repository. This is the single reference for what we
have, what we're waiting on, and what the next action is per source.

| # | Source | What it is | License | Vendored? | Blocker | Next action |
|---|---|---|---|---|---|---|
| 1 | **SBLGNT** | Greek NT (27 books) | CC-BY-4.0 + SBLGNT EULA | ✓ (existing) | — | Keep as-is |
| 2 | **WLC / UHB** | Hebrew Protestant OT | CC-BY-4.0 / CC-BY-SA-4.0 | ✓ (existing) | — | Keep as-is |
| 3 | **Swete LXX 1909–1930** | Greek LXX incl. all deuterocanonical books | Public Domain (author d. 1917) | ✓ (OCR text committed; full PDFs via `MANIFEST.md` with SHA-256 hashes) | — | Run vision-transcription pipeline |
| 4 | **Schechter & Taylor 1899** — *Wisdom of Ben Sira* | Hebrew Sirach MSS A & B (Cairo Genizah, first publication) | Public Domain | ✓ (PDF + OCR + page-index committed) | — | Run vision-transcription pipeline |
| 5 | **Lévi, *L'Ecclésiastique*, 1898–1901** | Hebrew Sirach MS B extension + MS C | Public Domain | Not yet | Archive.org filename encoding issue | Resolve download URL / try Gallica BnF |
| 6 | **Peters 1902** — *Der jüngst wiederaufgefundene hebräische Text* | Hebrew Sirach MSS B, C, D | Public Domain | Not yet | Identify clean archive source | Search archive.org / HathiTrust |
| 7 | **Marcus 1931** — *The Newly Discovered Original Hebrew of Ecclesiasticus* | Hebrew Sirach MS E | Public Domain (US, pre-1964 non-renewed); verify outside US | Not yet | Identify clean archive source | Search HathiTrust |
| 8 | **Cambridge Digital Library** (Taylor-Schechter) | High-res photos of Cairo Genizah Ben Sira fragments | Per-item terms (mostly research-permissive) | Not yet | Per-shelfmark license review | Fetch IIIF manifests by shelfmark |
| 9 | **Oxford Bodleian** digital collections | Additional Genizah Ben Sira photos | Per-item terms | Not yet | Per-item license review | Manual per-item fetch |
| 10 | **Masada Ben Sira scroll** (Mas1h) | Only pre-medieval Hebrew Sirach witness (Sir 39:27–43:30) | Restrictive | Acquisition in progress | Direct access | Integrate when available; use Swete Greek in interim |
| 11 | **Qumran Tobit fragments** (4Q196–4Q200) | Only Aramaic/Hebrew Tobit witnesses (≈20% of Tobit) | Restrictive | Acquisition in progress | Direct access | Integrate when available; use Swete Greek in interim |
| 12 | **Qumran Sirach fragments** (2Q18, 11QPsa) | Small DSS Sirach fragments | Restrictive | Acquisition in progress | Direct access | Integrate when available |

Legend: ✓ = acquired and vendored · ◐ = request in flight / partial · (blank) = acquirable but not yet pursued.

**Scholarly editions consulted during transcription (not reproduced):**
Beentjes 1997 (*The Book of Ben Sira in Hebrew*); Skehan & Di Lella 1987
(Anchor Bible 39); Ben-Ḥayyim 1973 (Academy of the Hebrew Language); the
Göttingen critical LXX editions; Fitzmyer 1995 (*Discoveries in the
Judaean Desert* Vol. XIX); Rahlfs-Hanhart 2006 (Stuttgart revised
critical LXX); and further literature as relevant per book. These works
inform our fresh transcription but are never copied into our published
output.

## Per-book drafting roadmap

The status of each book in scope, showing its most-original primary
source, its Greek fallback (for verses or passages where the original
is lost or damaged), and its overall readiness to enter Phase C
(drafting). Status updates as sources are transcribed.

| Book | Original language | Primary source for COB | Greek fallback (Swete) | Status |
|---|---|---|---|---|
| Tobit | Aramaic (lost for 80%; Qumran fragments cover ~20%) | Swete LXX (Long Recension from Codex Sinaiticus) | — (is primary) | Ready once Swete transcribed |
| Judith | Hebrew (lost entirely) | Swete LXX | — (is primary) | Ready once Swete transcribed |
| Greek Additions to Esther | Greek (original) | Swete LXX | — | Ready once Swete transcribed |
| Wisdom of Solomon | Greek (original) | Swete LXX | — | Ready once Swete transcribed |
| **Sirach (Ecclesiasticus)** | **Hebrew** (≈ ⅔ recovered) | Schechter 1899 (Hebrew, MSS A & B) + Lévi/Peters/Marcus for MSS C–F + fresh transcription from PD photos | Swete LXX for lost portions | Requires Schechter + Lévi + Peters + Marcus transcribed; Masada integrated when available |
| Baruch + Letter of Jeremiah | Hebrew (lost entirely) | Swete LXX | — (is primary) | Ready once Swete transcribed |
| Additions to Daniel (Susanna, Bel & the Dragon, Prayer of Azariah, Song of the Three) | Greek (original) | Swete LXX | — | Ready once Swete transcribed |
| 1 Maccabees | Hebrew (lost entirely) | Swete LXX | — (is primary) | Ready once Swete transcribed |
| 2 Maccabees | Greek (original) | Swete LXX | — | Ready once Swete transcribed |
| 1 Esdras | Greek (Semitic Vorlage lost) | Swete LXX | — (is primary) | Ready once Swete transcribed |
| Prayer of Manasseh | Greek | Swete LXX | — | Ready once Swete transcribed |
| Psalm 151 | Hebrew (partial at 11QPsa) | Swete LXX primary; Hebrew fragment integrated when available | — | Ready immediately from Swete |
| 3 Maccabees | Greek | Swete LXX | — | Ready once Swete transcribed |
| 4 Maccabees | Greek | Swete LXX | — | Ready once Swete transcribed |

## Translation pipeline

The same four-stage pipeline defined in METHODOLOGY.md applies:

1. **Source preparation** — vendored Rahlfs LXX under
   `sources/lxx/rahlfs/`. Textual variants noted in the per-verse
   YAML `source.text` and in footnotes where material.
2. **AI draft** — GPT-5.4 with the same prompt family used for the
   Protestant canon, adapted only in the source-edition field.
   Per-verse YAML emitted with full provenance (`ai_draft` block).
3. **Revision pass** — Claude Opus 4.7 reviews drafts per the
   criteria in REVISION_METHODOLOGY.md. Revisions are discrete git
   commits; the drafter's `ai_draft` metadata is preserved.
4. **Publication** — tagged release on GitHub, mobile bundle
   regenerated, footnote apparatus cited transparently.

These books receive the same level of rigor as the Protestant canon.
No corner-cutting because they are "deutero."

## Transcription accuracy — honest expectations

AI-vision transcription accuracy varies sharply by source material.
We state our expected accuracy by text type rather than claim
uniform rigor, so readers can calibrate their trust in our
deuterocanonical sources:

| Text type | Expected accuracy vs. established scholarship |
|---|---|
| **Typeset printed Greek** (Swete 1909) | **On par or better.** Modern vision LLMs handle clear 19th–20th-century polytonic Greek at 95–99% first-pass accuracy; the pipeline is faster, consistent, and reproducible. Multi-model cross-check (Claude Opus 4.7 + GPT-5.4 + Gemini 2.5 Pro) catches the remaining edge cases (accent placement, diacritic confusion). |
| **Typeset printed Hebrew** (Schechter 1899 printed transcription) | **On par.** Same profile as typeset Greek — clean typography, AI handles well. Multi-model cross-check + automated comparison against consultation-informed scholarly consensus catches subtle errors. |
| **Medieval Hebrew semi-cursive manuscript** (Cairo Genizah facsimile plates) | **Behind Beentjes alone on first pass; approaches parity with full pipeline over iterations.** Specialists have decades of context a single vision model does not. Our pipeline adds: (a) multi-model transcription with disagreement flagging, (b) cross-source verification against other PD publications that cover the same folio, (c) active consultation of published scholarship with documented divergences, (d) public repository + issue templates for community correction. Over iterations this approaches specialist-grade accuracy. |
| **Fragmentary damaged parchment** (Qumran Tobit 4Q196–4Q200, Masada Sirach) | **Specialist paleographers retain the edge.** We transcribe only what is legibly present on the physical fragment and mark lacunae as lacunae. We do not generate reconstructions of missing letters — both for accuracy reasons and for copyright reasons (per *Qimron v. Shanks*, 2000). Scholars' reconstructions are cited, not reproduced. |

**What we are not claiming.** We are not claiming machine parity with
Beentjes on manuscript plate transcription on a first pass, nor parity
with Fitzmyer on Qumran reconstruction. These are specialist works
produced over decades of career-deep engagement with specific material.

**What we are claiming.** The pipeline — fresh vision transcription
informed by consultation of all leading scholarship, multi-model
disagreement flagging, cross-source verification, and transparent
public iteration — produces source-texts adequate for translation work,
with every character auditable back to a public-domain photograph and
every divergence from published scholarship documented. That is
substantively equivalent to specialist-grade source fidelity for
translation purposes, which is what the deuterocanonical section of
the Cartha Open Bible is delivering.

## Consulting scholarship, reproducing nothing

The scholarly apparatus around Hebrew Sirach and Qumran Tobit is the
product of careers of specialist labor (Beentjes 1997 on Hebrew
Sirach; Fitzmyer 1995 and the DJD volumes on Qumran Tobit; Skehan &
Di Lella 1987; the Göttingen LXX critical editions for the Greek; among
many others). These works are indispensable to accurate translation,
and we consult them actively during our work.

What copyright restricts is **reproduction of their specific text**,
not consultation. This distinction is the same one that governs
every serious modern translation: a translator reads every major
scholarly edition, weighs every variant, is informed by every
argued reading — and then produces their own fresh work. The
published output is the translator's own creation, informed by the
literature but not copied from it. This is standard scholarly
practice; it is uncontroversial under copyright law; it is what
the NRSV, NABRE, ESV, and every other modern translation have
always done.

Our commitment:

- **We consult the leading scholarly editions actively during
  transcription and translation.** Beentjes 1997 for Hebrew Sirach,
  Fitzmyer 1995 for Qumran Tobit, Skehan & Di Lella 1987 for
  English Sirach, the Göttingen critical editions for LXX variants,
  and further literature as needed. Where we notice a divergence
  between our fresh transcription and established scholarship, we
  weigh the evidence, document our reasoning, and either revise our
  transcription or note the disagreement with explanation.
- **Our published transcription is our own creative work** —
  produced freshly from public-domain photographs, informed by
  consultation of all relevant scholarship, but not a reproduction
  of any scholarly edition's specific transcribed text. This is a
  fresh and independent transcription, not a compilation.
- **We cite scholarly conclusions in footnotes where they inform
  translation decisions** — which is fact-level citation, not
  reproduction of creative expression, and is uncontroversial under
  US copyright law (*Feist v. Rural Telephone Service*, 1991).
  Example footnote shape: *"Hebrew MS B at this verse reads
  differently from the Greek; the Greek appears to smooth an
  idiomatic Hebrew expression. See Beentjes (1997) and Skehan &
  Di Lella, Anchor Bible 39 (1987)."*

The practical outcome: our transcription pipeline is informed by
every scholar who has worked this material, while our output is
cleanly our own. That is the path to specialist-grade accuracy
without reproducing specialist-owned text.

## Labeling in the final product

In both the repository and the mobile app:

- A clear section header: **"Deuterocanonical Books (Apocrypha)"**
- An introductory note to the section explaining the canonical-status
  landscape across traditions, and naming that COB takes no position.
- Each book's header displays its canonical status at a glance:
  - *Canonical in: Roman Catholic, Eastern Orthodox*
  - *Considered useful but not canonical in: most Protestant traditions*
- Internal references (cross-references in commentary, reading plans,
  search results) treat these books as first-class citizens of the
  library while preserving the label.

The reader should never be confused about what they are reading and
which traditions receive it as Scripture.

## Phasing

**Phase A — Source acquisition (in flight, 2026-04-18).**
- ✓ Swete LXX vendored: DjVu OCR text in repo, full PDFs manifested
  at `sources/lxx/swete/MANIFEST.md` with SHA-256 hashes.
- ✓ Schechter 1899 *Wisdom of Ben Sira* vendored in repo
  (PDF + OCR, `sources/hebrew_sirach/schechter_1899/`).
- ◐ Masada Ben Sira scroll and Qumran Tobit fragment photographs:
  acquisition in progress.
- ◐ Fresh transcription pipeline from public-domain photographs
  scoped for Cairo Genizah MSS C–F (`sources/hebrew_sirach/
  genizah_photos/README.md`).

**Phase B — Vision-transcribe LXX and Hebrew Sirach working text.**
- Per-page vision-based transcription of Swete Greek into clean
  UTF-8 Greek with breathings and accents, committed to
  `sources/lxx/swete/transcribed/`.
- Per-folio vision-based transcription of Schechter 1899 Hebrew
  into clean UTF-8 Hebrew, committed to
  `sources/hebrew_sirach/schechter_1899/transcribed/`.
- Machine-readable verse indexes connect book/chapter/verse to
  source-text and source-image provenance.

**Phase C — Draft and revise translations.**
- Extend `tools/draft.py` to handle LXX and Hebrew Sirach source
  identifiers.
- Draft each deuterocanonical book from its most-original extant
  source per the per-book matrix above.
- Revision pass (Claude Opus) per `REVISION_METHODOLOGY.md`.
- Mobile bundle integration, tagged release.

**Phase D — Pre-medieval Hebrew & Aramaic enrichment (when available).**
- Fresh Aramaic transcription of Qumran Tobit fragments; integrate
  as Tobit primary source for the ~20% of verses they cover.
- Fresh Hebrew transcription of Masada Ben Sira; integrate as Sirach
  primary source for 39:27–43:30.
- Republish tagged release including Phase D sources.

**2 Esdras / 4 Ezra and the Ethiopian wider canon** (1 Enoch,
Jubilees, etc.) are not committed to any phase. If they are ever
added, it will be under a separate dedicated strategy document
specific to their distinct textual traditions.

### Phase summary table

| Phase | Work | Effort | Gating factor |
|---|---|---|---|
| **A — Source acquisition** | Vendor Swete LXX + Schechter 1899 | ✓ Done | — |
|  | Download Lévi 1901, Peters 1902, Marcus 1931 | 1 day | — |
|  | Fetch Cambridge Digital Library Genizah IIIF | 1 week | Per-shelfmark license review |
|  | Acquire Masada + Qumran Tobit photograph access | Timeline dependent on upstream | External |
| **B — Vision transcription** | Build `tools/transcribe_source.py` (page → image → vision LLM → clean UTF-8) | 2–3 days | — |
|  | Multi-model cross-check + disagreement queue | 2–3 days | — |
|  | Transcribe Swete LXX vols I–III (deuterocanonical sections, ~400 pages) | 2–3 weeks automated + iterative review | API throughput |
|  | Transcribe Schechter 1899 Hebrew Sirach typeset (~100 pages) | 1 week | — |
|  | Transcribe Genizah MSS C–F from PD facsimiles | 2–4 weeks | Hardest text; lowest accuracy first pass |
|  | Transcribe Masada + Qumran fragments (when photos available) | 1–2 weeks | Upstream access |
| **C — Pipeline extension** | Extend `tools/draft.py` for LXX + Hebrew Sirach source identifiers + cross-language source blocks in per-verse YAML | 2–3 days | — |
|  | Update `schema/verse.schema.json` for multi-source verses (primary + Greek parallel) | 1 day | — |
| **D — Drafting** | GPT-5.4 drafter on each book, per-verse YAML with full provenance | ≈ 1 week per book average | Source transcribed |
| **E — Revision** | Claude Opus 4.7 reviser per `REVISION_METHODOLOGY.md` | Ongoing | Drafts complete |
| **F — Publication** | Mobile bundle integration + tagged release + Phase 8 of `README.md` cadence | 1 day | Revision complete |

## Commitments

We commit, as a project, to:

1. **Equal rigor.** These books receive the same drafter/reviser
   pipeline, the same per-verse provenance, the same footnote
   standards as the Protestant canon. No shortcuts because they
   are deuterocanonical.
2. **Transparent canonicity labeling.** Every book's header shows
   its canonical status across major traditions. Readers are never
   misled about what they are reading.
3. **No doctrinal importation.** Translation decisions follow the
   same DOCTRINE.md principles. We do not soften readings to align
   with Protestant doubts about these books, nor expand readings to
   strengthen Catholic/Orthodox claims about them.
4. **Public scrutiny before publication.** This strategy document is
   published before any verse is drafted so the approach itself can
   be challenged.
5. **Honest limitations.** We document what our LXX-only approach
   does and does not capture. A reader who wants Hebrew Sirach
   variants at every verse will need to consult scholarly editions
   alongside COB. That is stated openly, not obscured.

## Why this honors the texts

These books are read as Scripture by hundreds of millions of
Christians and have been for two millennia. They shaped the
vocabulary of the New Testament (James echoes Sirach; Hebrews 11
lists Maccabean martyrs alongside the patriarchs). They were the
devotional library of Jesus's own world.

Translating them carefully, with provenance and honest footnotes,
under a free license, with the best tools we have — this honors
them as Scripture for those who receive them as Scripture, and as
early Jewish religious literature for those who do not. It refuses
the shortcut of deciding for the reader what counts.

That refusal is the whole point of the Cartha Open Bible.
