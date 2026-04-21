# 2 Esdras — per-book scope and source plan

2 Esdras (also called 4 Ezra / Latin Ezra / the Ezra Apocalypse) is
one of the most theologically weighty texts in the wider Christian
apocryphal tradition, but it sits outside our Swete/LXX pipeline
entirely. This document explains why, what we have decided to do
with it, and how to produce it cleanly.

> **Status: 2026-04-21.** In scope as an Appendix book. Source
> acquisition and Latin→English pipeline work pending.

## Why it's not in Phase 8 / Phase 9

Our Phase 8 corpus is our own OCR of **Swete's diplomatic edition
of Codex Vaticanus**. 2 Esdras is not in Codex Vaticanus — in fact,
it is not extant in Greek at all (outside a tiny papyrus fragment
for 15:57–59). Swete does not print it. Our Greek pipeline does
not apply.

Unlike every other book in the corpus so far, 2 Esdras has to be
translated from **Latin** (with Syriac as a cross-check for the
core chapters), not Greek. This is a separate, smaller sub-project
that runs after the Swete corpus ships.

## Textual situation

### The book is a composite

- **Chapters 3–14 = "4 Ezra"** — a Jewish apocalypse written in
  Hebrew or Aramaic around **c. 100 AD**, in the decades after the
  fall of the Second Temple (70 AD). The original Semitic text is
  **lost**. It was translated into Greek (also lost, save scraps),
  and from Greek into Latin, Syriac, Ethiopic, Armenian, Georgian,
  Arabic (two independent versions), and Coptic (fragmentary).
- **Chapters 1–2 = "5 Ezra"** — a Christian addition, attested
  **only in Latin**, probably 2nd–3rd century. Recasts Ezra as a
  prophet rejected by Israel with God turning to the Gentiles.
- **Chapters 15–16 = "6 Ezra"** — a Christian addition, attested
  **only in Latin** (plus POxy 1010 for 15:57–59 in Greek),
  probably 3rd century. Prophetic oracles against the nations.

The traditional Christian book "2 Esdras" combines all three into a
single 16-chapter text in the order 1–2, 3–14, 15–16. That is how
the KJV 1611 Apocrypha prints it and how we will present it.

### What survives and what we translate from

| Portion | Latin | Syriac | Ethiopic | Greek | Original |
|---|---|---|---|---|---|
| Chs 1–2 (5 Ezra) | ✓ | — | — | — | Latin is original |
| Chs 3–14 (4 Ezra) | ✓ | ✓ | ✓ | fragments | **lost** (Heb/Aram) |
| Chs 15–16 (6 Ezra) | ✓ | — | — | POxy 1010 (15:57–59 only) | Greek lost, Latin near-original |

### Modern critical editions

- **Bensly, 1895** — *The Fourth Book of Ezra, the Latin Version
  Edited from the MSS.* Cambridge. The critical Latin edition that
  recovered the "lost fragment" (7:36–105) omitted from most
  medieval MSS and therefore missing from the Vulgate and KJV
  1611. **Public domain. This is our base.**
- **Ceriani, 1883** — *Translatio Syra Pescitto VT*. Photographic
  edition of the Ambrosiana Syriac Peshitta. Contains the Syriac
  of 4 Ezra (chs 3–14). **Public domain. This is our cross-check
  for the core chapters.**
- **Stone, 1990** — *Fourth Ezra* (Hermeneia). Modern critical
  commentary and English translation. **Copyright. Zone 2 —
  consult only, not reproducible.**
- **Violet, 1910 / 1924** — GCS editions of the Latin and the
  oriental versions. Public domain (German critical apparatus).

## Canonicity

| Tradition | Status |
|---|---|
| Eastern Orthodox | Not canonical (Orthodox Study Bible omits it) |
| Roman Catholic | Vulgate appendix (not canonical post-Trent) |
| Protestant (historic) | KJV 1611 Apocrypha (complete, 16 chapters) |
| Slavonic / Russian Orthodox Bible | Canonical as "3 Ezra" |
| Ethiopian Orthodox | Canonical |
| Armenian Orthodox | Appendix |

No major Western canon currently includes it. Its historical
presence in the **KJV 1611 Apocrypha** is the primary reason for
its inclusion here.

## Why include it at all

The core (3–14) is one of the most theologically serious
apocalypses ever composed. It wrestles directly with the problem of
evil after the destruction of Jerusalem, articulates a pre-Christian
doctrine of the corrupted heart (*cor malignum*, 3:21–22) that
Augustine later leaned on, contains an explicit two-age eschatology,
describes a **dying Messiah** (7:28–29) in a Jewish text roughly
contemporary with the Gospels, gives one of the most detailed
Second Temple descriptions of resurrection and judgment (ch 7), and
closes with the foundational canon-formation narrative of Ezra
dictating 24 + 70 books (ch 14).

Modern Christians who read 2 Esdras 3, 7, 8, and 14 regularly
report it as among the most formative texts they encounter outside
the canonical 66. Excluding it from a project whose goal includes
"make serious old texts freely accessible in modern English" would
impoverish the reader for little methodological gain.

## Scope decision

**Include all 16 chapters.** Presentation is as an **Appendix**
book, clearly labeled as not canonical in most Western traditions.
Chapters 1–2 and 15–16 are translated and included, but flagged
editorially as later Christian additions distinct in origin from
the Jewish core.

### Rationale

- All 16 are what the KJV 1611 prints and what most English readers
  mean by "2 Esdras."
- Selectively omitting 1–2 and 15–16 would silently pick a scholarly
  side rather than letting the reader see the historical shape of
  the book.
- Honest labeling does more for the reader than editorial pruning.

## Editorial labeling in the text

Every chapter header and the book's own preface will surface the
compositional layers. Specifically:

- **Book-level headnote** (shown in app/website before ch 1 — see
  below).
- **Section header before ch 1:** *"5 Ezra (Christian addition,
  Latin only, c. 2nd–3rd century AD). These two chapters were
  added in Latin Christian circles and are not part of the original
  Jewish apocalypse. Preserved here because the KJV 1611 Apocrypha
  prints them in this position."*
- **Section header before ch 3:** *"4 Ezra (the original Jewish
  apocalypse, c. 100 AD). Composed in Hebrew or Aramaic after the
  fall of the Second Temple; surviving in Latin, Syriac, Ethiopic,
  and other versions; the Semitic original is lost."*
- **Section header before ch 15:** *"6 Ezra (Christian addition,
  Latin only, c. 3rd century AD). Prophetic oracles against the
  nations, appended to the Latin tradition of 4 Ezra and printed
  here because the KJV 1611 Apocrypha includes them."*
- **Footnote at 7:36:** *"Bensly's 'lost fragment' (7:36–105).
  This passage was cut from most medieval Latin manuscripts — very
  likely because it teaches that intercession for the damned is
  refused — and was therefore missing from the Vulgate and from
  the KJV 1611, which numbers verse 7:35 as immediately followed
  by 7:36 = 'And I answered and said, How...' picking up after the
  gap. Recovered by Bensly from a Spanish manuscript in 1875 and
  now restored in all modern editions."*
- **Footnote at 7:28:** *"'My son the Messiah shall die.' The
  Latin reads* filius meus Christus *with the death of the Messiah
  followed by 400 years of silence and then the resurrection. The
  Syriac and Ethiopic preserve similar readings. This is among the
  most striking Jewish messianic passages from the period."*

## Book-level headnote (draft for app / website)

This is the text that should surface above 2 Esdras in the reading
interface. Engineering should wire it into whatever mechanism
renders book intros.

> **2 Esdras (Appendix)**
>
> *Also called 4 Ezra or the Ezra Apocalypse. Not canonical in
> modern Catholic, Orthodox, or Protestant Bibles. Canonical in
> the Ethiopian and Slavonic traditions. Included in the Apocrypha
> of the 1611 King James Bible and in the appendix of the Latin
> Vulgate. Presented here because of its long reception history in
> the Christian tradition and because of its profound theological
> wrestling with the problem of evil, judgment, resurrection, and
> Messiah.*
>
> *The book is a composite. The core (chapters 3–14) is a Jewish
> apocalypse written in Hebrew or Aramaic around 100 AD, after the
> fall of the Second Temple. The original is lost; the text
> survives in Latin, Syriac, Ethiopic, and other ancient
> translations. Chapters 1–2 and 15–16 are later Christian
> additions preserved only in Latin. All three layers are
> included, labeled, and translated fresh for this edition.*
>
> *This translation is based on Bensly's 1895 critical Latin
> edition (Cambridge), with the Syriac Peshitta (Ceriani 1883)
> consulted for the core chapters. The "lost fragment" of 7:36–105,
> missing from the 1611 KJV and from most medieval Latin
> manuscripts, is restored to its place.*

## Clean-licensed acquisition path

### Primary: Bensly 1895 (critical Latin)

- **Full title**: R. L. Bensly (ed., completed by M. R. James),
  *The Fourth Book of Ezra: The Latin Version Edited from the
  MSS.* Cambridge: Cambridge University Press, Texts and Studies
  III.2, 1895.
- Prints the critical Latin text including the 7:36–105 fragment
  recovered from Codex Sangermanensis / Codex Ambianensis.
- **Public domain.** Archive.org: search
  `fourth book of ezra bensly 1895` or
  `cambridge texts and studies 1895`.
- This is the **base text for chs 3–14 and for chs 1–2, 15–16**.

### Secondary: Ceriani 1883 (Syriac Peshitta)

- **Full title**: A. M. Ceriani, *Translatio Syra Pescitto
  Veteris Testamenti ex Codice Ambrosiano sec. fere VI photolitho­
  graphice edita*. Milan, 1876–1883.
- Photographic facsimile of the 6th-century Ambrosianus B.21
  Peshitta MS. Contains the Syriac of 4 Ezra (chs 3–14).
- **Public domain.** Archive.org: search `ceriani peshitta` or
  `translatio syra pescitto`.
- Used as **cross-check for chs 3–14** where the Latin is uncertain
  or where scholarly consensus holds Syriac preserves a better
  reading.

### Tertiary: Violet 1910/1924 (GCS critical editions)

- **Full title**: Bruno Violet, *Die Esra-Apokalypse*, GCS 18
  (1910) and *Die Apokalypsen des Esra und des Baruch in
  deutscher Gestalt*, GCS 32 (1924).
- Public domain German critical editions with full apparatus
  comparing Latin, Syriac, Ethiopic, Armenian, Georgian, and
  Arabic.
- **Consult-only reference** for apparatus-level questions during
  adjudication.

### For POxy 1010 (Greek fragment of 15:57–59)

- Grenfell & Hunt, *The Oxyrhynchus Papyri* vol. VII (1910).
  Public domain. Archive.org.

## Recommended execution plan

When a session picks this up — after the Swete corpus ships:

1. **Download the PD sources.** Bensly 1895 (Latin, required),
   Ceriani 1883 (Syriac Peshitta, required for cross-check),
   Violet 1910 (German, optional apparatus reference), POxy 1010
   (Greek fragment, tiny).
2. **Vendor them under `sources/second_esdras/scans/`** with a
   MANIFEST.md carrying SHA-256 hashes and archive.org
   identifiers. Parallel structure to `sources/lxx/`.
3. **OCR the Latin** using `tools/greek_extra_pdf_ocr.py` adapted
   for Latin (simpler — Latin alphabet, well-understood by
   Gemini 3.1 Pro). Probably warrants a thin wrapper
   `tools/latin_pdf_ocr.py` with the Latin-specific prompt.
4. **OCR the Syriac chs 3–14** — this is harder (Estrangela
   script). Gemini 3.1 Pro handles Syriac; a specific prompt is
   needed. Treat Syriac OCR as consult-quality rather than
   base-quality.
5. **Build `2ES.jsonl`** at
   `sources/second_esdras/corpus/2ES.jsonl` with all 16 chapters,
   sourced from our Latin OCR. Follow the same verse-level schema
   as other books.
6. **Register book code `2ES`** in the book registry (parallel to
   how `MAN` is registered with zero Swete pages).
7. **Multi-source adjudication for chs 3–14**: compare our Latin
   OCR against Bensly's printed critical text and against the
   Syriac Peshitta readings (Zone 2 consult). Flag disagreements
   rather than silently harmonizing.
8. **Draft** using a **new Latin→English translator prompt**
   (not the existing Greek one). The prompt should explicitly:
   - Render *cor malignum* as "evil heart" or "corrupted heart"
     consistently (per 3:21–22 → 4:30 → 7:48 thread).
   - Preserve *Altissimus* / "the Most High" as a reverent divine
     title (not flattened to "God").
   - Keep Ezra's emotional register — grief, protest, complaint —
     rather than smoothing into polite devotional English.
   - Honor the seven-vision structure in section headings.
9. **Insert editorial labeling** (section headers before 1, 3, 15;
   footnotes at 7:28, 7:36) per the "Editorial labeling" section
   above.
10. **Wire the book-level headnote** (draft above) into the app /
    website rendering pipeline.
11. **Review pass** with special attention to the "harder
    teachings" (7:45–61, 8:38–41, 9:13–22) — the project's stance
    is to let these land, not smooth them away.
12. **Ship as Appendix.** Not counted toward the Apocrypha
    completion metric; listed separately as an Appendix book.
    `status.json` documents it as a separate track.

## Estimated effort

- Source acquisition: 1–2 hours (three PDFs: Bensly, Ceriani,
  Violet; plus archive.org identifier confirmation).
- Latin OCR pipeline adaptation: 2–3 hours (new wrapper, Latin
  prompt, validation against Bensly printed text).
- Syriac OCR: 2–4 hours (harder script, needs validation).
- Corpus assembly: 2 hours (16 chapters, ~400 verses).
- Adjudication: 3–4 hours (Latin vs Syriac for chs 3–14 is more
  nuanced than our existing Greek adjudication).
- Latin→English translator prompt: 2–3 hours to draft, test on a
  sample chapter, refine.
- Drafting: 4–6 hours (16 chapters, ~400 verses, longer because
  this is our first Latin book and the theology is dense).
- Editorial labeling + headnote wiring: 1–2 hours.
- Review pass: 2–3 hours.

**Total: ~20–30 hours of focused work.** Larger than Prayer of
Manasseh (which was ~2–3 hours) because it requires a new Latin
pipeline from scratch.

## Current gap status

- 2 Esdras is not in the LXX corpus and is not counted in the
  14-book Apocrypha completion metric.
- It is tracked here as a separate **Appendix book** with its own
  production path.
- When it ships, it appears in the app / website as "2 Esdras
  (Appendix)" with the headnote above, after the last canonical
  Apocrypha book, alongside Prayer of Manasseh if that has also
  shipped.
- Listed in `CHANGELOG.md` and `status.json` as an Appendix track
  distinct from the LXX/Apocrypha track.
