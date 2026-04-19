# Swete Septuagint (LXX) — Public Domain

**Status: in progress.** Swete's 1909–1930 *The Old Testament in Greek* is
our working Septuagint source. It is fully public domain and includes all
deuterocanonical books.

## Why Swete and not Rahlfs

Rahlfs 1935 is also public domain, but no clean CC-BY-4.0 digital
transcription of Rahlfs exists that we can vendor. The available digital
editions are either:
- `eliranwong/LXX-Rahlfs-1935` — CC BY-NC-SA 4.0 (non-commercial + share-alike,
  incompatible with CC-BY-4.0)
- `CenterBLC/LXX` — derived from the above, same license problem
- `CCAT/CATSS LXXM` — restrictive non-redistribution license
- STEPBible `TAGOT` — announced but not yet released as of 2026-04-18

Swete's 1909–1930 edition is on the Internet Archive as scanned PDFs and
contains every deuterocanonical book we need:

- **Vol. I** — Genesis through 4 Kingdoms (= 2 Kings)
- **Vol. II** — Chronicles through Ecclesiasticus (Sirach). Includes Tobit,
  Judith, Greek Esther with additions, Wisdom of Solomon, and Sirach.
- **Vol. III** — Hosea through 4 Maccabees. Includes 1-4 Maccabees,
  Baruch + Letter of Jeremiah, Greek Daniel with additions (Susanna,
  Bel, Prayer of Azariah, Song of the Three), plus Psalms of Solomon
  (not deuterocanonical but bundled).

Swete used a different manuscript base than Rahlfs (primarily Codex Vaticanus
with Sinaiticus and Alexandrinus as variants, vs. Rahlfs's broader eclectic
approach). For our purposes this is a feature rather than a bug — Swete is
closer to a single-manuscript base and easier to audit.

## What's vendored here

- `swete_vol1_djvu.txt`, `swete_vol2_djvu.txt`, `swete_vol3_djvu.txt` —
  Archive.org's automated OCR of the three volumes. **These are rough**
  (the OCR cannot handle polytonic Greek well). They serve as an archival
  reference and a search-index, not as the working source text.
- `MANIFEST.md` — archive.org URLs and SHA-256 hashes for the three full
  PDFs, which are too large to commit to git directly (~155 MB total).
  Fetch them with `curl` per the manifest instructions.

## What we use as the working source

The working source text for drafting is produced by **vision-based
transcription from the archival PDFs**:

1. We download a page image from archive.org (via the IIIF API or direct
   download pattern).
2. A vision-capable LLM transcribes the printed Greek into clean UTF-8
   with breathings, accents, and diacritics preserved.
3. The transcribed text is committed to `transcribed/` (created as pages
   are processed), alongside provenance metadata:
   - source URL (archive.org page image)
   - SHA-256 hash of the page image
   - transcription model + timestamp
   - human verification status
4. Per-book clean-text files accumulate in `transcribed/by_book/`
   (e.g. `TOB.txt`, `SIR.txt`, `1MA.txt`), one per deuterocanonical book.

This keeps the pipeline transparent and auditable: every character we
publish has provenance back to a specific public-domain page scan.

See `tools/transcribe_lxx.py` (planned) for the pipeline implementation.

## License

Swete's text is in the public domain (published 1909–1930; author died 1917).
Archive.org hosts the digitized scans under a non-copyright rights statement;
the underlying printed text carries no copyright.

Our fresh transcriptions of the text are released under **CC-BY 4.0** as part
of the Cartha Open Bible.

## Required attribution

When quoting from our transcription:

> Greek text transcribed from Henry Barclay Swete, *The Old Testament in
> Greek according to the Septuagint*, Vols. I–III (Cambridge University
> Press, 1909–1930), public-domain scans hosted at Internet Archive.
> Transcription by Cartha Open Bible, CC-BY 4.0.
