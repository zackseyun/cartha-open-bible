# Cairo Genizah Photographs — Fresh Transcription Pipeline

This directory holds fresh AI-vision transcriptions of Cairo Genizah
Ben Sira manuscripts from public-domain photographs, for use as
source material in the Cartha Open Bible.

**Our transcription is freshly produced from photographs; our work is
actively informed by the full scholarly literature.** Beentjes 1997,
Skehan & Di Lella 1987, Ben-Ḥayyim 1973, and every later scholarly
edition are consulted during transcription — that's how rigorous
translation is always done. Copyright restricts **reproduction** of
a scholar's specific transcribed text, not consultation of their
work. We read the literature, weigh the variants, then produce our
own independent transcription. Where we disagree with published
scholarship we document our reasoning in the folio-level provenance
file; where we agree we note the convergence.

What we **do not** do: copy any scholar's specific transcribed text
into our output. Our published transcription is our own creative
work.

## Photograph sources, in order of preference

### 1. Public-domain early-20th-century publications (first choice)

Several pre-1928 scholarly volumes reproduced the Genizah Ben Sira
manuscripts in facsimile plates and are now public domain:

- **Schechter & Taylor 1899** — MSS A and B (already vendored at
  `../schechter_1899/`)
- **Lévi, *L'Ecclésiastique*, 1898–1901** — includes additional MS B
  plates and MS C fragments; PD worldwide
- **Peters, *Der jüngst wiederaufgefundene hebräische Text des
  Buches Ecclesiasticus*, 1902** — MSS B, C, D; PD worldwide
- **Marcus, *The Newly Discovered Original Hebrew of Ecclesiasticus*,
  1931** — MS E; PD in US (pre-1964 non-renewed), to verify elsewhere
- **Knabenbauer, *Commentarius in Ecclesiasticum*, 1902** — includes
  photographic plates; PD worldwide

These are our primary path for pre-Masada Hebrew Sirach.

### 2. Contemporary permissively-licensed imagery

- **Cambridge Digital Library** (cudl.lib.cam.ac.uk) hosts the
  Taylor-Schechter Genizah collection, including Ben Sira shelfmarks.
  License terms vary per item; we verify per-shelfmark before using.
- **Oxford Bodleian Digital Collections** — public-domain ancient
  manuscripts. Similar per-item license verification.
- **JTS New York** and **BnF Paris** for their respective holdings.

Images from these collections are used only when their license
permits redistribution-derived works (which includes our fresh
transcription under CC-BY 4.0). When it does not, we use the same
image to inform our work but do not vendor it in this repo.

### 3. Friedberg Genizah Project (*not used*)

The Friedberg Genizah Project (genizah.org) aggregates high-quality
Genizah imagery but requires registration and explicitly restricts
redistribution. We **do not** use FGP images. If a researcher wants
to cross-reference our transcription with FGP, they can do so
independently; our provenance is always back to a public-domain
source.

## Pipeline (per-folio workflow)

1. **Identify the folio.** Match shelfmark (e.g., T-S 12.863) to
   content (e.g., MS A, folio covering Sirach 3:6–4:10).
2. **Locate a public-domain image.** Priority: Schechter 1899
   facsimile plates; fallback: Lévi 1901, Peters 1902, Marcus 1931.
3. **Download and hash.** SHA-256 the image; store provenance in
   `PROVENANCE.md`.
4. **Vision transcription.** Pass the image to a vision-capable LLM
   (GPT-5.4 or Claude Opus 4.7) with a prompt anchored in Hebrew
   paleographic conventions. Record the model + timestamp.
5. **Sanity check against Schechter 1899 typeset Hebrew** where the
   folio is in Schechter's coverage — this verifies the vision
   model's accuracy on a folio-by-folio basis.
6. **Commit** the transcription to `transcribed/MS_X/folio_Y.txt`
   with YAML front-matter recording source image, model, timestamp,
   and known issues (lacunae, damaged letters, ambiguous characters).
7. **Open for verification.** Every transcription is marked as
   "draft, community verification welcomed" and remains in that
   state until human review is logged via GitHub PR.

## Provenance policy

Every single transcribed character has a documented lineage:
folio image → SHA-256 → source publication → vision model → date →
human verification status. This lets any scholar audit our work
from the first committed character forward.

## License

Our fresh transcriptions are released under **CC-BY 4.0**.
