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

Tagged releases follow the `vMAJOR.MINOR.PATCH` convention. The first public
release is `v0.1-preview`.

## Directory structure

```
cartha-open-bible/
├── DEDICATION.md        Blessing and hope — to whom this work is offered
├── PHILOSOPHY.md        Why this translation exists, open-source posture, commitments
├── DOCTRINE.md          Theological commitments driving translation decisions
├── METHODOLOGY.md       Drafting and cross-check pipeline
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
