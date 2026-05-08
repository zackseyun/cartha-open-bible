# Testament of Judah — per-verse skeleton decision

This is a research-only memo. **No translation files were modified.** The
maintainer should read it end-to-end before any restructuring is attempted.

## TL;DR

The reported "20-of-26-chapter mismatch" is real but it is not what it
sounds like. There are **three independent problems** entangled in
the per-verse YAMLs, and only one of them is "skeleton mismatch":

1. **Project re-numbering is intentional and pervasive.** The project's
   English-narrative numbering does not, and was never intended to,
   match Charles 1908 α-verse numbering 1:1. Eight chapters demonstrably
   span a Charles boundary (e.g. ch4 absorbs Charles III.7-10 + IV.1-3).
   The chapter-level `source.text` is clean Charles α; the
   `translation.text` and per-verse YAMLs follow the project's own
   reader-surface segmentation.
2. **Per-verse `source.text` is contaminated v1 OCR slop on ~14 of 20
   deferred chapters.** These files predate the v2 source-fix.
   The chapter-level `source.text` was cleaned to v2; the per-verse
   files were never refreshed and still contain column-interleave,
   apparatus markers (`β,`, `A-b*`, `S¹`, `|` separators), and stray
   Charles verse numbers inside the body.
3. **A handful of per-verse skeletons are genuinely incomplete or
   broken.** ch14 is missing `002.yaml` outright; ch26 has four
   per-verse YAMLs whose `source.text` are byte-for-byte identical
   (paste error); ch19 has only one per-verse YAML for a chapter whose
   chapter-level English is a single sentence (other content was
   re-allocated to ch20).

Re-splitting all 20 chapters to clean Charles α-verse boundaries would
**delete intentional translator work** (the cross-chapter narrative
re-flow) and would not address problem (2) at all. The right call is
the opposite: keep the project's existing per-verse skeleton as the
authoritative reader surface, fix the localized data corruption, and
file Charles α-verse anchors as metadata rather than as primary keys.

## Per-chapter survey (20 deferred chapters)

Counts: `Charles α` = max numbered marker in
`sources/.../normalized_v2/judah/chXX.txt` (with the implicit verse 1
counted). `Project YAMLs` = file count under
`translation/.../judah/NNN/`. `Eng#` = max numbered marker found in the
chapter-level `translation.text` (0 = unnumbered prose).
Category key: **(a)** re-split needed, **(b)** keep project
consolidation, **(c)** off-by-one accept, **(d)** ambiguous —
maintainer call. **(e)** local data bug independent of skeleton.

| Ch | Charles α | Project YAMLs | Eng# | Category | Notes / recommendation |
|----|-----------|---------------|------|----------|------------------------|
| 2  | 8 | 7 | 0 | **c** | Off-by-one. Project v1-v7 already track Charles α 1-7; α v8 ("Καὶ λέοντα") is one short clause that the project fused into v7. Accept current. |
| 3  | 10 | 6 | 6 | **b+e** | Project consolidates Charles 1-10 into 6 reader-surface verses. Per-verse YAMLs are **also carrying v1 source garbage** (column interleave, `Ἀχὼρ | 3. *Τὸν` etc.). Keep skeleton; refresh `source.text`. |
| 4  | 3 | 8 | 8 | **b+e** | Project verse 1-4 = Charles IV.1-3; project verses 5-8 = **content from Charles III.7-10** that the project moved here. Source-comment in `ch04.txt` documents the re-flow. Keep skeleton; refresh `source.text` from clean v2 (and from ch3 v2 for verses 5-8). |
| 5  | 7 | 7 | 1 | **e** | Counts already match. The defect is per-verse `source.text` carrying column-interleave from the v1 transcription. Keep skeleton; refresh source. |
| 6  | 5 | 2 | 0 | **a** | Genuine under-population. Charles VI has five short narrative verses (battles at Chozeba, Jobel, Shilom, Machir, the women rolling stones). Project has only two per-verse YAMLs, and the chapter-level English actually only translates Charles 1-2. Recommend: either expand to 5 verses (translate Charles 3-5) **or** add a maintainer note that the chapter is intentionally short. Decision needed. |
| 8  | 3 (in source) / 24 (English) | 2 | 42 | **a** | Mismatch is huge. The chapter-level English has 42 numbered verses (it absorbs the entire Tamar/Shua + wine-warning arc) but only `001.yaml` and `002.yaml` exist. Re-split is mandatory. Estimate: **~22 new YAMLs**. Maintainer should also confirm whether 42 is correct or a typo/marker artifact. |
| 10 | 6 | 5 | 0 | **c+e** | One verse short. Per-verse v1-v5 cover Charles 1-5; Charles 6 (the brief death-of-Onan coda) is fused into project v5. Source.text is dirty. Accept skeleton; refresh source. |
| 11 | 5 | 5 | 0 | **c** | Counts match. Source mostly clean. Accept. |
| 13 | 8 | 5 | 0 | **b+e** | Project consolidates Charles 1-8 into 5 reader-surface verses. Source.text dirty in v3, v5. Keep skeleton; refresh source. |
| 14 | 8 | 7 (002 missing) | 0 | **e** | The skeleton has a hole — verse `002.yaml` does not exist while `001`, `003`-`008` do. Either rename downward (003→002 etc.) or create a new `002.yaml`. Likely a forgotten draft. Maintainer call. |
| 15 | 5 | 5 | 1 | **c** | Counts match. Light source noise on v3. Accept; light refresh. |
| 16 | 4 | 5 | 5 | **c** | Project has one *more* verse than Charles. Reading v1: it begins mid-sentence (`θεοῦ22 ὅτι23 *κἂν βασιλέως...`) — that's overflow from ch15. The English chapter text is well-formed at 5 verses. Accept project's 5; refresh sources. |
| 17 | 5 | 3 | 0 | **b** | Project consolidates Charles 1-5 into 3 reader-surface verses (programmatic exhortation, short). Keep. |
| 18 | 6 | 9 | 5 | **d** | Project has *more* per-verse YAMLs than Charles. Looking at the per-verse content, project v1-v4 correspond to Charles XVII.5 + XVIII.1-3 (boundary re-flow again), and project v5-v9 to Charles XVIII.2-6 with one further split. **This is genuinely confusing**, possibly accidental. Maintainer should review. |
| 19 | 4 | 1 | 0 | **a** | Chapter-level English is a single 55-character sentence ("My children, the love of money leads to idolatry."). Charles XIX is four verses long; the rest of its content was relocated to ch20 (project ch20 v1 source.text begins `ὁδηγεῖ³, ὅτι⁴...` — the continuation of XIX.1). Either (i) accept the project's deliberate 1-verse ch19 + 5-verse ch20 layout, or (ii) restore Charles boundaries. **Maintainer call.** Note this is the same boundary-re-flow pattern as ch3-4. |
| 20 | 5 | 5 | 5 | **b+e** | Counts match but the *content* is shifted: project v1 = Charles XIX.1 leftover, project v5-v9 cover Charles XX.1-5. Skeleton is fine; source.text needs refresh. |
| 22 | 3 | 2 | 0 | **c** | Off-by-one consolidation. Charles XXII.3 is brief; project fuses it. Accept. |
| 23 | 5 | 3 | 0 | **b** | Project consolidates Charles 1-5 into 3. Accept. |
| 24 | 6 | 5 | 5 | **c+e** | Off-by-one consolidation. Per-verse `source.text` is full of two-column interleave (`α, β, S A` headers visible in v1). Refresh source urgently. |
| 26 | 4 | 4 | 0 | **e** | Counts match — but **all four per-verse YAMLs have identical `source.text`** (paste-error). This is a hard data bug. Fix immediately. |

Summary of categories: **(a) re-split** = 3 chapters (6, 8, 19);
**(b) keep project consolidation** = 6 (3, 4, 13, 17, 18, 20, 23);
**(c) off-by-one / accept** = 7 (2, 10, 11, 15, 16, 22, 24);
**(d) ambiguous** = 1 (18 reviewed under (b) but flagged); **(e) data
bug independent of skeleton** = ~12 chapters overlapping with the
above (3, 4, 5, 10, 13, 14, 15, 16, 18, 20, 24, 26).

## Top-level recommendation

**Keep the project's per-verse skeleton as the authoritative reader
surface for Judah. Treat the Charles α-verse numbering as a
secondary cross-reference, not as the primary index.** Then attack
the three problems independently:

1. **Two truly under-populated chapters (6, 8, 19) need a translation
   decision, not a re-split.** Are they intentionally short? If yes,
   add a chapter-level normalization note and stop. If no, draft the
   missing verses. ch8 is the most consequential — 22 missing verses
   is a chapter of work.
2. **The "skeleton hole" in ch14 and the duplicate-source bug in
   ch26 are unambiguous data bugs.** Fix them deterministically.
3. **The per-verse `source.text` corruption is a separate
   refresh-from-v2 task.** It does not depend on any skeleton call
   and can be done mechanically by re-extracting fragments from the
   already-clean chapter-level `ch{NN}.txt` files.

### Why NOT re-split to Charles

Pro: machine-aligned cross-references with other Charles editions and
with secondary literature; predictable verse counts.

Con (decisive): the project has already invested translation labor in
boundary re-flow (ch3↔4, ch19↔20, the long ch8 narrative). Re-splitting
would either discard that work or require re-translating to Charles
boundaries, doubling the cost of every affected chapter. The current
skeleton is also more *readable* — Charles' verse 8 of chapter 2 is
just "Καὶ λέοντα" ("And a lion."); the project sensibly fuses it
into v7. Imposing Charles boundaries would litter the reader UI with
single-clause verses.

### Why NOT keep current verbatim

Pro: zero immediate work.

Con (decisive): problems (2) and (3) above are real defects that
break trust in the per-verse provenance pages on cartha.com. A
reader landing on `peoples-open-bible/verse?ref=JUD.4.4` should not
see `β, Α, S¹ ἀνεῖλον⁵². *οἱ δὲ λοιποί⁵³ ἔφυγον.` as the source.

### Effort estimate

* **Source.text refresh across all 20 deferred chapters**: ~120-140
  per-verse YAMLs to re-key. Each takes ~30s of careful copy with a
  visual check against `chNN.txt`. **~1.5 hours of focused work, or
  scriptable** if the project trusts a "split chapter source on
  numbered-marker boundaries, then assign by project verse-content"
  pipeline. ch4, ch3, ch19, ch20 boundary re-flows would need
  per-chapter overrides.
* **ch6 expansion** (if expanding): 3 new per-verse YAMLs — ~1 hour
  with an LLM draft + manual edit.
* **ch8 expansion** (if expanding): 22 new per-verse YAMLs — ~6-8
  hours, or one full drafting-pass session.
* **ch19 (if Charles boundaries restored)**: 3 new per-verse YAMLs +
  re-anchor ch20 v1's content back into ch19 — ~1.5 hours.
* **ch14 fill / re-number, ch26 four-way de-dup**: ~30 minutes total.

If we ship **option "keep skeleton + refresh sources only"**, the
total cost is ~2-3 hours and resolves the public-facing source
quality issue without any translation re-work.

## Maintainer-only calls

These are project-design questions only the maintainer can answer:

1. **ch6, ch8, ch19**: are these short by design or by accident?
2. **ch14**: should `002.yaml` be created (translate Charles XIV.2)
   or should `003`-`008` be renamed down by one?
3. **ch18 over-population**: is the 9-verse skeleton intentional, or
   was a draft accidentally split into too many parts?
4. **Charles α-verse mapping as metadata**: should each per-verse YAML
   gain an explicit field like `charles_alpha_verses: ["IV.1","IV.2"]`
   so cross-references survive even though the project skeleton
   diverges?

## Validation

`yaml.safe_load` succeeds on every chapter-level Judah YAML and every
per-verse YAML inspected. **No translation files were modified by
this audit.** The only output is this document.
