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

### Source editions

**Primary:** the 1935 **Rahlfs Septuagint** (Alfred Rahlfs, ed.,
*Septuaginta: Id est Vetus Testamentum graece iuxta LXX
interpretes*, Stuttgart). Public domain. This is the same edition
every major modern Bible that includes the Apocrypha translates from
(NRSV, NABRE, Orthodox Study Bible, Jerusalem Bible for most books).

We plan to vendor the LXX from **STEPBible data**
(https://github.com/STEPBible/STEPBible-Data), an MIT-licensed
transcription with morphological tagging.

**Cross-reference (for footnotes only):** Hebrew Sirach manuscripts
(Cairo Genizah A–F, Masada scroll, Qumran 2Q18 and 11QPsa) and
Qumran Aramaic Tobit fragments (4Q196–200) are referenced for
textual-critical footnotes — *not* republished. See "Honoring
scholarship without reproducing it" below.

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

## Honoring scholarship without reproducing it

The scholarly apparatus around Hebrew Sirach and Qumran Tobit is the
product of careers of specialist labor (Beentjes 1997 on Hebrew
Sirach; Fitzmyer 2003 and the DJD volumes on Qumran Tobit, among
others). We respect that work. We also do not need to reproduce it.

Our commitment:

- **We translate from the LXX.** The Greek is the operative textual
  witness for this corpus in every major modern edition (NRSV,
  NABRE, Orthodox Study Bible). We follow that precedent.
- **We cite scholarly textual-critical conclusions in footnotes** —
  which is fact, not creative expression, and is uncontroversial
  under US copyright law (*Feist v. Rural Telephone Service*, 1991).
  Example footnote shape: *"Hebrew MS B at this verse reads
  differently from the Greek; the Greek appears to smooth an
  idiomatic Hebrew expression. See Beentjes (1997) and Skehan &
  Di Lella, Anchor Bible 39 (1987)."*
- **We do not republish copyrighted transcriptions** of fragmentary
  Hebrew or Qumran Aramaic text. If a future phase adds a
  cross-reference apparatus for these fragments, the text would
  come from fresh independent transcription of public-domain
  photographs (Friedberg Genizah Project, Cambridge Digital Library,
  Israel Antiquities Authority images), not from copying scholarly
  editions.

This is how the NRSV, NABRE, and Orthodox Study Bible have handled
the same material for decades. It is legally clean and it honors
the scholarship as scholarship rather than as raw material.

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

**Phase 1 — LXX-only translation (target: after NT completes).**
- Vendor Rahlfs LXX from STEPBible.
- Extend `tools/draft.py` to handle LXX source identifiers.
- Draft all books in the scope table above from Greek alone.
- Revision pass, mobile bundle integration, tagged release.

**Phase 2 — Textual-critical footnote enrichment (optional).**
- Add footnotes referencing Hebrew Sirach and Qumran Tobit variants
  by citing published scholarship (not reproducing transcriptions).
- Revise drafts where secondary-source consultation reveals better
  readings.

**Phase 3 — Independent Hebrew Sirach apparatus (long-term, optional).**
- Fresh transcription of Cairo Genizah Sirach manuscripts from
  public-domain photographs.
- Published as parallel cross-reference text under CC-BY 4.0.
- Explicitly not a competitor to Beentjes 1997 — a fresh independent
  reading for audit transparency.

**2 Esdras / 4 Ezra and the Ethiopian wider canon** (1 Enoch,
Jubilees, etc.) are not committed to any phase. If they are ever
added, it will be under a separate dedicated strategy document
specific to their distinct textual traditions.

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
