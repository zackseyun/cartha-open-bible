# The Cartha Open Bible
*Translated from the original Greek and Hebrew*

> God bless all believers, and all who are earnestly drawn to God and
> seeking Him. The hope of this translation is to create more critical
> thought and more open discussion of God's Word. — see [DEDICATION.md](DEDICATION.md)

**An open, transparent English Bible with auditable, commit-level
provenance for every translation decision.**

Released under **CC-BY 4.0** — anyone may use, adapt, redistribute, or
commercialize this translation with attribution. **See [PHILOSOPHY.md](PHILOSOPHY.md)
for the full statement on openness, transparency, and our theological
commitments.**

## Three things that make this different

1. **We translate from the originals, not from other English translations.**
   Source texts are the SBLGNT (Greek NT) and the Westminster Leningrad
   Codex / unfoldingWord Hebrew Bible (Hebrew OT) — the openly-licensed
   critical editions closest to what the NT and OT authors actually wrote.

2. **Every translation decision is publicly documented.** Every verse is a
   file in this repository with the source text, the English rendering, the
   key lexical choices (source word, chosen gloss, alternatives considered,
   lexicon entry, rationale), any contested theological readings with
   alternatives preserved, and the AI model and prompt that drafted it.

3. **Every verse is reproducible.** Given the source text, the prompt hash,
   and the model identifier, any third party can re-run the LLM pipeline
   and verify our documented draft. No other English Bible in history has
   offered this.

## Why this is possible now

Open-source infrastructure, frontier AI models as drafting tools, and modern
reproducibility standards together enable a kind of transparent translation
that was not feasible in any previous era — a translation where every
decision is documented, every verse is reproducible, and anyone with the
source text and the prompt can re-run the draft.

See [PHILOSOPHY.md](PHILOSOPHY.md) for the theological and historical
rationale.

## How COB reads — compared to NKJV and NIV

Two verses that illustrate what COB does differently, and why.

### Philippians 1:1

| | Rendering |
|---|---|
| **COB** | "Paul and Timothy, **slaves** of **Messiah** Jesus, to all the saints in Messiah Jesus who are in Philippi, together with the **overseers** and deacons:" |
| NKJV | "Paul and Timothy, bondservants of Jesus Christ, To all the saints in Christ Jesus who are in Philippi, with the bishops and deacons:" |
| NIV | "Paul and Timothy, servants of Christ Jesus, To all God's holy people in Christ Jesus at Philippi, together with the overseers and deacons:" |

- **δοῦλοι → "slaves"** (not "servants" or "bondservants"). In 1st-century Greco-Roman use, δοῦλος meant literal ownership of a person. "Servant" softens what Paul actually claimed; "bondservant" is a translator-invented neologism that avoids the weight. COB uses the accurate word and relies on the contextual layer to restore what the word meant to Paul's audience (not what it connotes in modern American English).
- **Χριστοῦ → "Messiah"** (translated, not transliterated). "Christ" has become a name in English; Paul wrote a title. "Messiah" restores the Jewish messianic claim Paul was making.
- **ἐπισκόποις → "overseers"** (not "bishops"). "Bishops" imports the later ecclesial office that didn't exist in 1st-century Philippi.

### Romans 3:25

| | Rendering |
|---|---|
| **COB** | "whom God put forward as an **atoning sacrifice** through faith in his blood, to demonstrate his righteousness, because of the **passing over** of previously committed sins." |
| NKJV | "whom God set forth as a propitiation by His blood, through faith, to demonstrate His righteousness, because in His forbearance God had passed over the sins that were previously committed" |
| NIV | "God presented **Christ** as a sacrifice of atonement, through the **shedding of his blood**—to be **received by faith**. He did this to demonstrate his righteousness, because in his forbearance he had left the sins committed beforehand unpunished" |

- **NIV inserts three phrases not in the Greek**: "Christ," "shedding of," and "received by faith." Each is a defensible interpretation — but it's embedded in the main text where the reader can't see it's a choice.
- **ἱλαστήριον → "atoning sacrifice"** — alternatives ("propitiation," "mercy seat") preserved in footnotes with rationale.
- **πάρεσιν → "passing over"** preserves Paul's specific Greek distinction between παρίημι (overlook) and ἀφίημι (forgive). NIV collapses this to "left unpunished."

### The philosophy behind these choices

COB's choice is **lexical accuracy in the main text + contextual understanding in a companion layer** — not pastoral softening of the translation itself.

"Slaves of Messiah Jesus" is harder on a modern reader's first pass than "servants of Christ Jesus," but it's what Paul actually wrote. Where a word's ancient meaning differs from modern English connotations, the responsibility is on the **reading experience** — the rationale recorded in each verse's YAML, footnotes, the in-app **Original context** AI tool, the public discussion forum — to restore the meaning. Not on the translation to quietly round it off.

That's why NIV's Romans 3:25 is illustrative of what COB avoids: a *good* interpretation invisibly embedded in the main text. The reader can't see it's a choice; they can't audit it; they can't disagree with it. COB makes every such choice visible and defensible.

**Is "slave" true to δοῦλος?** As close as a single English word can be. No single English word fully captures the ownership + submission + paradoxical honor + LXX "servant of YHWH" echo that Paul packed into δοῦλος. That's why one-tap context matters: the word is the foundation; the meaning lives in the layer you can read into.

## License

The translation is released under **CC-BY 4.0** — the canonical open-content
license. You may use, adapt, redistribute, or commercialize this work with
attribution. **Anyone may fork it, translate it into other languages,
include it in commercial products, or build derivatives without permission.**
We never paywall scripture. See [LICENSE](LICENSE) and [PHILOSOPHY.md](PHILOSOPHY.md).

Source texts retain their original licenses (see [sources/README.md](sources/README.md)).

## Doctrinal stance

Translation decisions follow the commitments in [DOCTRINE.md](DOCTRINE.md).
Declaring our stance up front is a form of honesty — critics can assess our
output against our stated commitments rather than guessing at hidden biases.

## Methodology

See [METHODOLOGY.md](METHODOLOGY.md) for the drafting pipeline, cross-check
protocol, and reproducibility verification.

## The Deuterocanonical Books (Apocrypha)

The Cartha Open Bible includes the Deuterocanonical books — Tobit, Judith,
Wisdom of Solomon, Sirach (Ecclesiasticus), Baruch, 1–4 Maccabees, and
others — as a clearly labeled section. See [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md)
for the full strategy; in brief:

### Why we include them

These books are canonical in the **Roman Catholic** (Trent, 1546),
**Eastern Orthodox** (Synod of Jerusalem, 1672), and **Oriental Orthodox**
traditions, and were included in **Luther's 1534 German Bible** and the
**original 1611 King James Version** as a middle section between the
Testaments. Their removal from most modern Protestant Bibles is a
19th-century development driven primarily by printing economics at the
British and Foreign Bible Society — not theological consensus.

Excluding them would be making a theological editorial decision *before*
the reader ever sees the text. That is the opposite of what the Cartha
Open Bible exists to do. Our mission is transparency and auditability —
present the textual tradition; let the reader and their faith community
judge what they affirm as canonical.

**We take no position on canonicity.** Including these books is not an
assertion that they carry the same authority as the Protestant canon.
Excluding them would be an assertion that they do not. We translate and
publish; the reader decides.

### How we honor them

These books receive the **same rigor as the Protestant canon** — same
drafter/reviser pipeline, same per-verse YAML with full provenance,
same license (CC-BY 4.0). No corner-cutting because they are "deutero."

Each book is translated from **the most-original extant text we can
lawfully access**:

- For books composed in Greek (Wisdom of Solomon, 2 Maccabees, the
  additions to Esther and Daniel), the LXX *is* the original — there
  is nothing behind it. Source: Swete's public-domain 1909–1930
  Septuagint.
- For books where the Hebrew or Aramaic original is lost (1 Maccabees,
  Judith, Baruch, 1 Esdras), the LXX is the oldest surviving witness.
  Same source.
- For **Sirach**, we translate primarily from the Hebrew where it
  survives — from Schechter & Taylor's public-domain 1899 edition
  of Cairo Genizah MSS A and B, and from fresh AI-vision
  transcriptions of the other manuscripts from public-domain
  photographs.
- For **Tobit**, we translate from the LXX Greek (Long Recension,
  supported by Codex Sinaiticus) and plan to incorporate the Qumran
  Aramaic fragments as a primary source for the ~20% of verses they
  cover, pending a licensing request to the Israel Antiquities
  Authority.

### How they are labeled

In both the repository and the mobile app:

- A clear section header: **"Deuterocanonical Books (Apocrypha)"**
- An introductory note explaining the canonical-status landscape across
  traditions.
- Each book's header shows its canonical status at a glance:
  *"Canonical in: Roman Catholic, Eastern Orthodox. Considered useful
  but not canonical in: most Protestant traditions."*
- Internal references (cross-references, reading plans, search results)
  treat these books as first-class citizens while preserving the label.

The reader should never be confused about what they are reading or which
traditions receive it as Scripture.

### The scholarship-integrity commitment

We consult the leading scholarly editions actively during our work —
Beentjes 1997 for Hebrew Sirach, Fitzmyer 1995 for Qumran Tobit,
Skehan & Di Lella 1987, the Göttingen critical LXX editions, and
further scholarship as needed. That consultation is how modern
translation has always been done: read everything, weigh every
variant, produce fresh work. Copyright law governs **reproduction**,
not reading — and consultation of scholarship to inform our own
fresh translation is standard, uncontroversial scholarly practice.

What we **do not** do is vendor or reproduce copyrighted scholarly
transcriptions (Beentjes's specific Hebrew text, the DJD volumes'
Qumran transcriptions, Rahlfs digital editions under restrictive
licenses, etc.). Every source text in this repository is either
public-domain by age or freshly produced by us from public-domain
photographs under CC-BY 4.0.

Where established scholarship informs a translation decision, we
cite it in footnotes — fact-level citation, not reproduction of
creative expression, uncontroversial under US copyright law
(*Feist v. Rural*, 1991). This combination — fresh transcription +
active consultation of the scholarly literature + transparent
citation — is exactly how the NRSV, NABRE, and Orthodox Study
Bible produce their Apocrypha sections. It's how serious
translation actually works.

### Why this honors the texts

These books are read as Scripture by **hundreds of millions of
Christians**, and have been for two millennia. They shaped the
vocabulary of the New Testament — James echoes Sirach; Hebrews 11
lists Maccabean martyrs alongside the patriarchs; the Magnificat
echoes Judith's prayer. They were the devotional library of Jesus's
own world.

Translating them carefully, with provenance and honest footnotes,
under a free license, using the best tools we have — this honors them
as Scripture for those who receive them as Scripture, and as early
Jewish religious literature for those who do not. It refuses the
shortcut of deciding for the reader what counts.

That refusal is the whole point of the Cartha Open Bible.

## Current status

The project is in its initial AI-drafting phase. Every verse in this
repository was produced by a frontier AI model, with full provenance, and
is released as a draft — not as a finalized translation. What you are
reading is exactly what the AI produced, with the rationale for every
decision visible alongside it. The repository is public so the process is
inspectable from the first commit forward.

## Contributing

Found a verse you'd translate differently? Open an issue using one of the
templates under `.github/ISSUE_TEMPLATE/`. Engagement is welcomed from
scholars, pastors, and lay readers. Our commitment is to respond publicly
to every substantive concern.

## Release cadence

The translation is built and released phase-by-phase, with each phase a full
set of complete books (not partial books):

- Phase 1: Pauline epistles (Romans through Philemon)
- Phase 2: Gospels + Acts
- Phase 3: General epistles + Revelation
- Phase 4: Torah (Genesis through Deuteronomy)
- Phase 5: Former Prophets (Joshua through 2 Kings)
- Phase 6: Writings (Psalms, Proverbs, Job, Chronicles, etc.)
- Phase 7: Latter Prophets (Isaiah, Jeremiah, Ezekiel, Twelve)
- Phase 8: Deuterocanonical books (Tobit through 4 Maccabees, from LXX). Corpus complete as of 2026-04-20 (13 books, 6,337 verses, 98.9% high-confidence scan-adjudicated transcription). Translation drafting begins in Phase 9. See [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md), [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md) (three-zone scholarly-source policy), and [REVISION_LATER.md](REVISION_LATER.md) (deferred-source integration).

Tagged releases follow the `vMAJOR.MINOR.PATCH` convention. The first public
release is `v0.1-preview`.

## Directory structure

```
cartha-open-bible/
├── DEDICATION.md        Blessing and hope — to whom this work is offered
├── PHILOSOPHY.md        Why this translation exists, open-source posture, commitments
├── DOCTRINE.md          Theological commitments driving translation decisions
├── METHODOLOGY.md       Drafting and cross-check pipeline
├── REVISION_METHODOLOGY.md  How committed drafts are revised (reviser roles, revision criteria)
├── DEUTEROCANONICAL.md  Strategy for including the Deuterocanonical / Apocrypha books
├── CHANGELOG.md         Phase-by-phase release notes
├── LICENSE              CC-BY 4.0
├── schema/
│   └── verse.schema.json    JSON Schema for per-verse YAML
├── sources/             Vendored source texts (see sources/README.md)
├── translation/         Per-verse YAML (translation/nt/<book>/<chap>/<verse>.yaml)
├── tools/               draft.py, cross_check.py, verify.py, consistency_lint.py
├── outreach/            Correspondence with publishers (ESV, NLT, etc.)
└── .github/
    └── ISSUE_TEMPLATE/  Public disagreement and concern templates
```
