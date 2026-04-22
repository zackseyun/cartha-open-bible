# Why this translation exists

Every major modern English Bible is the product of a closed process. A
committee of scholars makes thousands of translation decisions behind closed
doors; readers receive the finished text; the reasoning behind any given
word choice — why *doulos* was rendered "servant" here and "slave" there,
why the footnote elevates one reading over another — is almost never
surfaced to the people actually reading scripture.

This worked for centuries because it had to. Assembling the scholarship for
a Bible translation required publishers, institutional funding, and
closed-room deliberation. The opacity wasn't a choice — it was the cost of
getting the work done at all.

It isn't any longer.

## The moment this becomes possible

Three things are true now that were not true a decade ago:

1. **Open source infrastructure** — public repositories, issue trackers,
   collaborative editing — is free, instant, and globally accessible. A
   reader anywhere in the world can audit a translation decision the moment
   it's committed.

2. **Frontier AI models** — Claude, GPT, Gemini — can produce competent
   drafts of biblical Greek and Hebrew translation with full lexical
   reasoning, exposing every decision they make.

3. **Modern reproducibility standards** — "same input, same output" applied
   to translation means any third party with the source text, the prompt,
   and the model identifier can regenerate the draft and verify it matches.
   Nothing like this exists in the history of Bible translation.

Together, these make something new possible: a translation where every
decision is documented, every disagreement is public, every verse is
reproducible, and every word can be traced back to the Greek or Hebrew it
came from — in under 60 seconds, from a phone, anywhere in the world.

That is the Cartha Open Bible.

## What we are translating

We translate directly from public-domain and openly-licensed scholarly
editions of the original-language texts, across all three canonical sections
of the Christian Bible.

**New Testament** (27 books):

- **SBLGNT** (Greek New Testament, ed. Michael W. Holmes) — the closest
  legally-available approximation to the autographs the NT authors wrote.

**Old Testament — Protestant canon** (39 books):

- **Westminster Leningrad Codex** and **unfoldingWord Hebrew Bible** — based
  on the Leningrad Codex (1008 AD), the oldest complete Hebrew Bible
  manuscript in existence.

**Deuterocanonical / Apocrypha** (14 books — Tobit, Judith, Wisdom of
Solomon, Sirach, Baruch, Letter of Jeremiah, Additions to Esther, Additions
to Daniel, 1 Maccabees, 2 Maccabees, 3 Maccabees, 4 Maccabees, 1 Esdras,
Prayer of Manasseh, Psalm 151. See [DEUTEROCANONICAL.md](DEUTEROCANONICAL.md)
for why we include these and which Christian traditions receive each as
canonical):

- **Swete LXX** (Henry Barclay Swete, *The Old Testament in Greek According
  to the Septuagint*, Cambridge, 1909–1930) — a public-domain diplomatic
  edition of Codex Vaticanus. This is our Greek source for every
  deuterocanonical book. We transcribe it ourselves from the archival page
  scans using AI vision and release the transcription under CC-BY 4.0.
- **Sefaria Ben Sira (Kahana edition, CC0)** and **Schechter 1899** — the
  public-domain Cairo Geniza Hebrew witness to Sirach. Roughly two-thirds of
  Sirach survives in Hebrew; we translate from the Hebrew where it survives
  and from the Greek where it does not.
- **Neubauer 1878 Hebrew Tobit** (via Sefaria, Public Domain) — a Hebrew
  back-translation of Tobit, used as a Semitic-phrasing reference alongside
  the Greek Long Recension (Codex Sinaiticus).
- **WLC MT parallels for 1 Esdras** — 1 Esdras is a Greek recomposition of
  2 Chronicles 35–36, Ezra, and Nehemiah 7–8. We cross-reference each 1
  Esdras verse to its Hebrew parallel in our WLC corpus, with the "Story of
  the Three Youths" (3:1–5:6) treated as Greek-only material with no Hebrew
  parallel.

We are not paraphrasing or smoothing an existing English translation. We are
translating from the same sources the scholarly community works from — the
Greek and Hebrew — applying documented translation philosophy to each verse,
with every decision auditable.

## What "transparent" actually means here

Every verse in this translation is a file in this repository. Each file
contains:

- The **source text** (Greek or Hebrew) being translated
- The **English rendering** that ships to readers
- Every **lexical decision** made — the source word, the chosen English
  gloss, the alternatives considered, the lexicon consulted, and *why* the
  chosen gloss was preferred
- Every **theologically-contested reading**, with the alternative preserved
  in footnotes rather than buried
- The **AI model**, **prompt hash**, and **timestamp** of the draft
- A **git commit history** documenting every revision

If you disagree with a rendering, you don't have to send a letter to a
publisher and hope for a reply. You open an issue on GitHub, cite the
specific verse, and engage publicly. We commit to responding substantively
to every serious concern. When we revise, the revision is itself a commit
with documented rationale. Nothing happens in private.

This is transparency in the same sense scientific papers are transparent:
we show the data, we show the methods, we show the reasoning, and we invite
the rest of the world to check our work.

## Current status

The project is in its initial AI-drafting phase. Every verse you read in
the repository is exactly what a frontier AI model produced, with the full
rationale visible alongside it. We don't currently have a formal scholarly
review process, and we don't pretend to — the drafts are released as
drafts, and the repository is public so the reader can see the process
from the first commit forward, unvarnished.

This is the honest starting point. If a scholarly review process emerges
later, it will be announced publicly and documented in the repository.
Until then, what you see is what the AI produced.

## Open by principle, not by default

We release this translation under **Creative Commons Attribution 4.0
International (CC-BY 4.0)** — the canonical open-content license. This
means:

- **Anyone may use it** — in apps, websites, books, sermons, study
  curriculum, audio Bibles, video content, academic papers.
- **Anyone may use it commercially** — publish a paid study Bible, sell an
  app, build a paid tool. No royalties flow to us. No permission required.
- **Anyone may create derivative works** — paraphrases, adaptations,
  commentaries, translations into other languages, revisions.
- **Anyone may redistribute it**, including modified versions.
- Attribution is the only requirement: credit the Cartha Open Bible, link
  to the license, and indicate if you made changes.

This is a deliberate theological choice, not a pragmatic one. Every major
Bible before 1900 was effectively public domain — the KJV, Geneva, Tyndale,
Luther's German, Wycliffe. Paid licensing of scripture is a modern
innovation, not a historical norm. Our commitment is to recover the older
pattern: *freely you have received, freely give* (Matthew 10:8).

We do not want to own a Bible. We want to help produce one, hand it to the
church, and have people read it.

## What this is not

Several things it helps to say explicitly:

- **Not a finished translation.** What's in the repository is a draft. It
  will have errors, awkward renderings, and passages that will need
  revision. Every release tag makes this explicit.
- **Not a replacement for scholarship.** We stand on the shoulders of
  centuries of Greek and Hebrew lexicography, textual criticism, and
  theological scholarship. Every lexical decision cites the lexicons
  (BDAG, HALOT, LSJ, Louw-Nida) the academy already uses.
- **Not a denominational product.** COB does not commit to a specific
  denominational or creedal stance. Where the source texts presuppose
  theological claims, the translation reflects those claims as the
  texts present them, not as imposed commitments. Contested readings
  are preserved in footnotes, not smoothed away. See
  [DOCTRINE.md](DOCTRINE.md) for the full translation-stance document.
- **Not a study Bible.** Footnotes document translation decisions, not
  devotional application.
- **Not finished.** This is an ongoing project. We ship phase-by-phase,
  book-by-book, with every stage transparently marked as draft.

## How to engage

- **Read it.** When a book is drafted, read it. Tell us what lands and what
  doesn't.
- **Critique it.** File an issue on GitHub for any verse you'd translate
  differently. Lexical disagreements, theological disagreements, and general
  concerns all have templates.
- **Cite it.** In academic work, sermons, or published material, cite the
  Cartha Open Bible with a link back. Attribution keeps the paper trail
  visible.
- **Fork it.** If you have a specific scholarly disagreement you want to
  pursue, fork the repository and publish your alternative. Our provenance
  records travel with the fork.
- **Translate it.** CC-BY 4.0 permits derivative translations into other
  languages. A translator working from the Cartha Open Bible into any other
  language inherits the full provenance chain back to the Greek and Hebrew.

## Our commitment

We commit to:

- **Never paywall scripture.** The text will always be free to read.
- **Never hide decisions.** Every translation choice remains documented,
  publicly inspectable, and reproducible.
- **Never silence disagreement.** Public issues remain open; responses are
  public; revisions are public.
- **Never claim authority the text doesn't have.** This translation is an
  AI-produced rendering of ancient documents into modern English, released
  openly. It is not itself inspired. Scripture is.

The Word belongs to the church. We are stewards of a process, not owners of
a text.
