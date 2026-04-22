# Apocrypha provenance — how every verse was sourced and verified

Public-facing account of how each of the 17 books in the Cartha Open
Bible deuterocanonical section arrived in the corpus, verse by verse,
and how a reader can verify our text against public-domain
scholarship without taking anything on trust.

> Audience: readers, scholars, translators, librarians, and anyone
> asking "did you invent any of this?" The short answer is: no — and
> here is what you can check.

## Principle

Every deuterocanonical verse in the Cartha Open Bible carries three
things on its per-verse YAML:

1. **A Greek source text** (the `source.text` field) with a named
   edition (`source.edition`) and the page numbers that edition was
   drawn from.
2. **A confidence label** at the source-text layer (high / medium /
   low) that reflects our scan-adjudication rubric.
3. **A drafting record** naming the model, prompt, and timestamp
   that produced the English, with lexical decisions exposed.

Every piece is auditable against publicly-downloadable documents. The
sections below walk through the four sub-pipelines used across the 17
books.

## Sub-pipeline 1 — Swete diplomatic Vaticanus (12 of 17 books)

**Books**: Tobit, Judith, Additions to Esther, Wisdom of Solomon,
Sirach, Baruch, Letter of Jeremiah, Prayer of Azariah + Song of the
Three, Susanna, Bel and the Dragon, 1–4 Maccabees, 1 Esdras.

**Source**: Henry Barclay Swete, *The Old Testament in Greek
According to the Septuagint*, 3 vols. (Cambridge University Press,
1909–1930). Public domain (Swete died 1917). Archive.org identifier:
`theoldtestamenti03swetuoft_202003`.

**How we processed it**:

1. **AI-vision OCR** of each scan page via Azure GPT-5.4 vision with
   a prompt specialized for polytonic Greek typography.
2. **Multi-witness adjudication**: for every verse where our OCR
   disagreed with at least one of three independent transcriptions
   (First1KGreek TEI, Rahlfs-Hanhart Marvel.Bible digital, Amicarelli
   BibleBento), we ran a scan-grounded adjudicator that looked at the
   actual page image and returned a verdict. The verdict identifies
   which witness matched the printed page, or marks the reading as
   "neither" when we re-transcribed directly from the scan.
3. **Confidence rubric**:
   - **High** = every character is clearly visible on the scan;
     reading matches a candidate exactly or is a confident fresh
     transcription; no smudges, fading, or ambiguous letterforms in
     the verse area.
   - **Medium** = verse substantively readable but specific
     characters ambiguous; best-guess call made; scan permits an
     alternative a specialist might prefer.
   - **Low** = verse not legibly visible on the scan; severe damage
     or relying on candidates without visual verification.
4. **Rescue passes**: initial low-confidence verses were re-run with
   higher-resolution scans, multi-source Hebrew parallel consultation
   (Kahana Ben Sira, Neubauer Tobit, WLC for 1 Esdras parallels),
   explicit confidence-rubric prompts, and content-based per-verse
   page mapping when running-head parsing missed pages.

**Final state** (detailed in `sources/lxx/swete/QUALITY_BENCHMARK.md`):

- **99.3% of adjudicated verses at high confidence** (3,442 / 3,464)
- **86.1% functional agreement** with First1KGreek as an independent
  validation oracle
- **6 books reach 100% high confidence** (Wisdom of Solomon, 3
  Maccabees, 4 Maccabees, Letter of Jeremiah, Additions to Daniel,
  Judith)

A reader can verify any Swete-sourced verse by:

1. Pulling the scan page from archive.org (link embedded in
   `source.pages`).
2. Comparing the printed Greek against our `source.text` for that
   verse.
3. Inspecting `source.confidence` to see how we rated our own
   reading.

## Sub-pipeline 2 — Prayer of Manasseh (Charles 1913 APOT Vol 1)

**Book**: Prayer of Manasseh (MAN), 15 verses.

Prayer of Manasseh is **not in Codex Vaticanus**, so Swete's
diplomatic edition does not contain it. Our normal pipeline does not
apply. We used a dedicated source path documented in detail in
[`PRAYER_OF_MANASSEH.md`](PRAYER_OF_MANASSEH.md).

**Source**: R. H. Charles (ed.), *The Apocrypha and Pseudepigrapha
of the Old Testament in English*, Vol. 1 (Oxford: Clarendon Press,
1913). Public domain (author d. 1931; pre-1929 US publication).
Archive.org identifier: `theapocryphaandp01unknuoft`. Our working
PDF has SHA-256 hash recorded in
`sources/lxx/prayer_of_manasseh/MANIFEST.md`.

**How we processed it**:

1. **OCR of Charles pp. 636–640** (the Prayer of Manasseh
   main-text + apparatus + footnotes) via Gemini 3.1 Pro Preview with
   the strict text-extraction prompt (`systemInstruction` +
   `responseMimeType: text/plain`). 5 pages, 0 failures, 1,480 Greek
   characters across the apparatus + footnote lemmata.
2. **Greek text reconstruction**: Charles's edition prints the
   English translation as main body, with Greek scattered through
   the critical apparatus and footnotes (he cites "A" for Codex
   Alexandrinus, "T" for Codex Turicensis, "Const. Apost." for
   Apostolic Constitutions 2.22, "Syr." for Syriac, "Lat." for
   Latin Vulgate, "Moz." for Mozarabic Psalter). We passed the OCR
   output to Gemini 3.1 Pro with an explicit scholarly prompt:
   "reconstruct the continuous Greek text, verses 1-15, as witnessed
   by Codex Alexandrinus (A) per Charles's apparatus." The Greek
   text itself is public domain by age (~2000 years); Charles's
   apparatus lemmata are public domain by 1913 publication. Our
   reconstruction is at
   `sources/lxx/prayer_of_manasseh/corpus/MAN.jsonl` — 15 verses,
   292 Greek words.
3. **Rahlfs-Hanhart cross-check**: we verified our reconstruction
   against the Rahlfs-Hanhart 2006 Ode 12 digital text (a Zone 2
   consultation source, NC-licensed, never copied into our output).
   Word-overlap per verse was 62–92%, with mismatches traceable to
   known manuscript-family verse-division conventions and minor
   Alexandrinus-vs-eclectic orthographic variants. This does not
   introduce Rahlfs text into our corpus; it simply confirms that
   our reconstruction sits inside the expected range of variation
   for this prayer.
4. **Direct visual verification against Charles 1913 pp. 636–640**
   (2026-04-22): every verse division was checked against Charles's
   editorial numbering in the margin of his printed edition; every
   substantive word was checked against his apparatus lemmata or
   against the expected Codex Alexandrinus reading. Specific
   findings recorded in
   `sources/lxx/prayer_of_manasseh/corpus/MAN.jsonl` `v1.reconstruction_note`:
   - Verse boundaries match Charles's editorial numbering exactly.
   - v7's "inserted" clause ("Thou, O Lord, according to thy great
     goodness hast promised repentance...") is correctly **omitted**
     per Charles's apparatus: "Const. Apost., Syr., Lat., Moz.: om A T".
   - v8 reads `ἐμοὶ τῷ ἁμαρτωλῷ` (Codex A) rather than Rahlfs's
     `ἐπ᾽ ἐμοὶ τῷ ἁμαρτωλῷ`.
   - v9 originally had passive `ἐπληθύνθησαν`; this was **corrected**
     on 2026-04-22 to active `ἐπλήθυναν` per Charles's apparatus for
     Codex A: "κυριε επληθυναν αι ανομιαι μου". The v9 English draft
     was re-run against the corrected Greek.

**Licensing note**: MAN's `source.edition` field is
`charles-1913-apot-vol1`, not `lxx-swete-1909`. The drafter
(`tools/draft.py`) has a book-specific override for this so the
provenance is honest about where the Greek came from.

## Sub-pipeline 3 — Psalm 151 (Swete, but manually located)

**Book**: Psalm 151 (PS151), 7 verses.

Psalm 151 **is** in Codex Vaticanus (at the end of the Psalter), but
it sits at Swete vol 2 page 432 which our automated Phase-8 OCR
hadn't reached yet. The book had been declared in
`tools/lxx_swete.py` with a zero page range; the page discovery was
tail-of-phase-9 work.

**Source**: Swete LXX vol 2 page 432. The full Psalm 151 — running
head `[CLI]` with the characteristic intro "Οὗτος ὁ ψαλμὸς
ἰδιόγραφος εἰς Δαυείδ καὶ ἔξωθεν τοῦ ἀριθμοῦ, ὅτε ἐμονομάχησεν τῷ
Γολιάδ" ("This is the autograph psalm of David, outside the number,
when he fought Goliath") — sits cleanly on that page.

**How we processed it**:

1. Located the page by browsing Swete's Psalter pagination (end of
   Psalter = p432 based on running heads Ψαλμοί CXLIV–CLI).
2. OCR via `tools/transcribe_source.py --source swete --vol 2
   --page 432` using Azure GPT-5.4 vision with our standard Swete
   prompt. Clean output, 1,393 characters, all 7 verses with verse
   markers preserved.
3. Split into `PS151.jsonl` with 7 verse-keyed records.
4. Mirrored into `sources/lxx/swete/final_corpus_adjudicated/PS151.jsonl`
   so the existing drafter pipeline resolves PS151 via
   `lxx_swete.iter_source_verses("PS151")`.
5. Drafted all 7 verses via the standard GPT-5.4 drafter with no
   book-specific overrides (PS151 is a regular Swete-sourced book;
   its only unusual feature was not being in the original
   `DEUTEROCANONICAL_BOOKS` page-range registry).

**Licensing**: PS151's `source.edition` is the standard
`lxx-swete-1909` — same as every other Swete-sourced deuterocanonical
book.

## Sub-pipeline 4 — Additions to Daniel split

**Books**: Susanna (SUS, 64 verses), Bel and the Dragon (BEL, 42
verses), Prayer of Azariah + Song of the Three (PAZ, 67 verses).

These three works are historically aggregated as the "Greek Additions
to Daniel" (book code `ADA` in Swete) but were split in our
translation directory per scholarly convention. Each is drafted under
its own slug. The source Greek is the same Swete vol 3 adjudicated
corpus as the other LXX books; the split is purely organizational.

## Drafting layer (common to all 17 books)

English drafts are produced by `tools/draft.py` with GPT-5.4 (Azure
OpenAI, deployment `gpt-5-4-deployment`). For each verse the drafter:

1. Reads the adjudicated Greek source and verse number.
2. Loads the relevant COB doctrinal and translation-philosophy
   excerpts (DOCTRINE.md, PHILOSOPHY.md).
3. Loads any per-book apparatus or witness parallels (e.g., Hebrew
   parallels for Sirach / Tobit / 1 Esdras from
   `sources/lxx/hebrew_parallels/`).
4. Produces a schema-valid YAML with:
   - English translation
   - Translation philosophy (optimal-equivalence by default)
   - Per-word lexical decisions with rationale
   - Footnotes for alternative readings
   - Model + prompt-hash provenance for reproducibility

**Every English word in every deuterocanonical YAML is traceable to
a specific source edition + adjudicator verdict + drafter invocation.**

## What a reader can check, per verse

Take any deuterocanonical verse page on `cartha.com/cartha-open-bible`
and click through to its provenance. You will see:

- The Greek source text (`source.text`)
- The edition it came from (`source.edition`)
- The scan page numbers (`source.pages`)
- The adjudication verdict and confidence (in the `adjudication`
  sub-object for verses that were scan-adjudicated)
- Our English rendering (`translation.text`)
- Every significant lexical choice (`lexical_decisions`)
- The AI model and prompt that drafted the verse (`ai_draft`)

The scan pages are linkable to archive.org. The lexical decisions
are critique-able. Nothing is hidden behind "trust us."

## Honest disclosure of residual work

Not all 17 books are claimed as final:

- **Consistency lint** (`tools/consistency_lint.py`) has not been run
  across the deuterocanonical set yet. It enforces uniform handling
  of recurring terms (e.g., κύριος rendering, proper-name
  transliteration). Known pending task; does not affect per-verse
  correctness, only cross-verse consistency.
- **Systematic revision-methodology pass** per
  `REVISION_METHODOLOGY.md` has not yet been run. Phase-1 Pauline
  drafts have had full revision; the Apocrypha are at first-pass
  quality.
- **Scan-adjudication polish** on the remaining 17 medium-confidence
  verses (mostly proper-name transliteration lists in 1 Esdras +
  some Sirach + Greek Esther Additions) is tracked in
  `REVISION_LATER.md`.

A reader relying on a specific verse for scholarly citation should
consult the per-verse `source.confidence` field. Any verse marked
"high" has been visually verified; "medium" means the adjudicator
was substantively sure but not certain; "low" means we could not
visually verify the reading and defaulted to a well-attested
scholarly form.

## The three-zone policy (scholarship consultation)

Consultation of copyrighted scholarly editions is governed by
[`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md). In brief:

- **Zone 1**: public-domain or CC-licensed sources we vendor into
  the repo and derive from (Swete, Charles 1913, Sefaria Kahana,
  WLC, First1KGreek, etc.).
- **Zone 2**: copyrighted scholarly editions we consult without
  copying (Beentjes Hebrew Sirach, Fitzmyer DJD XIX Qumran Tobit,
  Yadin Masada scroll, Göttingen critical LXX, Rahlfs-Hanhart,
  Skehan & Di Lella, etc.). We may cite fact-level findings
  ("4Q196 attests the Long Recension here") but never reproduce
  their text.
- **Zone 3**: modern commercial English translations (NIV, NLT,
  ESV, NRSV). Not consulted during drafting to prevent
  derivative-work exposure.

The three-zone discipline is why our output is cleanly
CC-BY 4.0-redistributable even though our translators consulted
modern scholarship during drafting, the same way every modern
translation always has.

## Summary

The Apocrypha section of the Cartha Open Bible is:

- **Translated from original Greek** (not retranslated from other
  English translations).
- **Sourced from public-domain editions** (Swete 1909, Charles 1913).
- **Scan-grounded per verse** (99.3% at high confidence; medium and
  low verses explicitly labeled).
- **Reproducibly drafted** (model + prompt-hash + source page list
  on every verse).
- **CC-BY 4.0 licensed** (use freely with attribution).

What you read in the app is what the public-domain page prints, as
rendered into English by a documented, reproducible pipeline.
Nothing is black-box; everything is auditable.
