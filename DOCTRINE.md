# Doctrinal Stance

This document states the theological commitments that guide every translation
decision in the Cartha Open Bible. Declaring our stance is an act of honesty:
critics can assess our output against our stated commitments rather than
guessing at hidden biases.

> **Status: first draft.** This document will be refined by the project
> founder and review board before the first public release. Input from
> reviewers and advisors is welcomed via GitHub issues.

## Affirmations

The Cartha Open Bible is produced within the bounds of historic,
ecumenical Christian orthodoxy. The following creeds are affirmed as
summaries of essential Christian doctrine:

- The Apostles' Creed
- The Nicene Creed (381 AD, including the *homoousios* language)
- The Definition of Chalcedon (451 AD, on the two natures of Christ)

Within those bounds, the translation does not advocate for a particular
denominational distinctive (Reformed, Arminian, Wesleyan, Anabaptist, etc.)
unless the Greek or Hebrew unambiguously supports one reading over another.

## Translation philosophy

The Cartha Open Bible aims at **optimal equivalence**: a middle path
between formal ("word-for-word") and dynamic ("thought-for-thought") approaches.

Specifically:

1. **Original-language primacy over translation tradition.** Where long-standing
   English renderings reflect translation-tradition inertia rather than the
   source text's plain sense, we favor the source. Example: translating
   *doulos* as "slave" rather than "servant" in contexts where the term's
   bonded nature is theologically salient (Rom 1:1, Phil 1:1).

2. **Translate titles; transliterate names.** Christological titles are
   translated to preserve meaning (*Christos* → "Messiah", not "Christ"
   where context supports; *Kyrios* → "Lord"). Personal names are
   transliterated by standard conventions.

3. **Preserve theological tension rather than resolve it.** Where the
   source is genuinely ambiguous on a contested interpretive question
   (e.g., *pistis Christou* — "faith in Christ" vs. "faithfulness of
   Christ"), we render one in the main text and preserve the alternative
   in a footnote, documenting the decision in the per-verse YAML.

4. **Gender-accurate over gender-neutral.** Where the Greek or Hebrew
   is grammatically masculine and carries representative or generic force
   ("man" for humanity, "brothers" for mixed-gender siblings), we render
   with the English form that matches the source's intent, annotated in
   footnotes where inclusivity is contextually relevant.

5. **Consistency of key terms, or documented exception.** A given Greek
   or Hebrew word should receive a consistent English gloss across the
   translation, unless context demands variance — in which case the
   variance is documented per-verse with a rationale. The
   `consistency_lint.py` tool enforces this at commit time.

6. **Readable modern English, not archaic or academic.** The target reader
   is a literate 18–35-year-old English speaker. Vocabulary should be
   accessible without flattening theological weight. We avoid both
   ecclesiastical jargon ("propitiation" is footnoted, not required) and
   informality that undersells the text's gravity.

## Contested terms

The following terms appear frequently and carry heavy theological weight.
Our default rendering and rationale are recorded here. Per-verse variance
is documented in the individual YAML files.

| Greek / Hebrew | Default English | Alternatives considered | Rationale |
|---|---|---|---|
| Χριστός *Christos* | Messiah (where title; Christ where name-like) | Christ | Preserves Hebraic messianic context |
| κύριος *Kyrios* | Lord | LORD, Master | Matches covenantal and NT usage |
| δοῦλος *doulos* | servant / slave (context-dependent) | bondservant | Uses "slave" where the bonded nature is salient |
| πίστις *pistis* | faith | faithfulness, trust | Main text: faith; footnote alternatives where contested |
| δικαιοσύνη *dikaiosynē* | righteousness | justice | Both renderings preserved in footnotes for Pauline passages |
| ἱλαστήριον *hilastērion* | atoning sacrifice | propitiation, mercy seat | Dynamic rendering for accessibility; alternatives footnoted |
| ἀγάπη *agapē* | love | charity (archaic) | Lexical cognates in source kept |
| σάρξ *sarx* | flesh (literal) / sinful nature (metaphorical) | — | Context-dependent; per-verse documented |
| יְהוָה YHWH | the LORD | Yahweh, Jehovah | Follows Jewish reverence tradition + LXX pattern |
| אָדָם *adam* | man / humankind (context) | — | Gender-accurate per context |

## What the translation is not

To prevent misunderstanding:

- **Not a paraphrase.** Every English rendering is tied to a specific source-text
  word or phrase, documented in the per-verse YAML.
- **Not a study Bible.** Footnotes document translation decisions, not doctrinal
  application or devotional commentary.
- **Not a denominational product.** The review board is intentionally
  cross-denominational within ecumenical orthodoxy.
- **Not produced solely by AI.** LLMs produce drafts; named human reviewers
  sign every verse. No verse ships without a signed human review.
- **Not a first-century English approximation.** We aim at modern English
  that honors source-language meaning, not at archaism.

## Change log for this document

Material changes to this document are themselves commits. Before a verse is
reviewed against a changed stance, prior versions of the stance are preserved
in git history and linked from the per-verse YAML where relevant.
