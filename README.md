# The Cartha Open Bible
*Translated from the original Greek and Hebrew*

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
   alternatives preserved, the AI model and prompt that drafted it, the
   cross-check scores across three frontier models, and the named human
   reviewer's signature.

3. **Every verse is reproducible.** Given the source text, the prompt hash,
   and the model identifier, any third party can re-run the LLM pipeline
   and verify our documented draft. No other English Bible in history has
   offered this.

## Why this is possible now

Open-source infrastructure, frontier AI models as drafting tools, and modern
reproducibility standards together enable a kind of transparent translation
that was not feasible in any previous era. The AI is not the translator —
named human scholars review and sign every verse. The AI makes the
scholar's bottleneck tractable so the work can be done in the open.

See [PHILOSOPHY.md](PHILOSOPHY.md) for the theological and historical
rationale.

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
protocol, human review workflow, and reproducibility verification.

## Review board

See [REVIEWERS.md](REVIEWERS.md) for the named scholars reviewing and signing
verses. No verse ships to readers until a reviewer on this list has signed it.

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
├── PHILOSOPHY.md        Why this translation exists, open-source posture, commitments
├── DOCTRINE.md          Theological commitments driving translation decisions
├── METHODOLOGY.md       Drafting, review, and signing process
├── REVIEWERS.md         Named review board with credentials
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
