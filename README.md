# The Cartha Translation

A new English translation of the Bible, produced with transparent, auditable,
commit-level provenance for every translation decision.

## Why this exists

Every major modern English Bible translation is a closed process. A committee
decides what the text should say; readers receive the output; disagreements
are handled in private correspondence, if at all. The reasoning behind any
given word choice is rarely surfaced to the reader.

The Cartha Translation inverts that. Every verse carries a machine-readable
record of:

- The source text consulted (SBLGNT for NT, WLC / unfoldingWord Hebrew Bible for OT).
- The lexical decisions made (which Greek or Hebrew word, which lexicon entry,
  which English gloss, what alternatives were considered and why they were rejected).
- Any theologically contested readings with alternatives preserved in footnotes.
- The AI model, prompt, and timestamp that produced the draft.
- Cross-check results across multiple LLMs.
- The human reviewer who signed off, with their credentials and signature.
- A link to public discussion on the verse.

Every change is a signed git commit. Every disagreement has a permanent URL.
Every verse is reproducible — given the same source, prompt, and model, you
can re-run the draft yourself and confirm the output.

## License

The translation is released under **CC-BY 4.0**. You may use it for any
purpose, including commercial, with attribution. See [LICENSE](LICENSE).

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
cartha-translation/
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
