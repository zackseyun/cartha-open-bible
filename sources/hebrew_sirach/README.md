# Hebrew Sirach (Ben Sira) — Source Materials

Sirach (also called Ecclesiasticus) was composed in Hebrew around 180 BC
by Yeshua ben Eleazar ben Sira in Jerusalem. The Greek translation by his
grandson (c. 132 BC) is what was preserved in the Septuagint tradition
and is the operative text for every major modern translation.

Roughly **two-thirds of the original Hebrew text has been recovered**
from:

- **Cairo Genizah manuscripts A, B, C, D, E, F** (10th–12th century
  copies of earlier Hebrew), discovered by Schechter in 1896 onwards
- **Masada scroll** (c. 100 BC, covers Sirach 39:27–43:30)
- **Qumran fragments** (2Q18, 11QPsa — small)

Our goal is to translate Sirach *primarily from the Hebrew* where we
have it, consulting the Greek where the Hebrew is lost or damaged.
This is more faithful to the book's composition history than an
LXX-only approach would be.

## Clean-licensed source path

Every modern Hebrew Sirach scholarly edition (Beentjes 1997, Skehan &
Di Lella 1987, Ben-Ḥayyim 1973) is copyrighted and cannot be vendored
into a CC-BY-4.0 project. We use two **public-domain** paths instead:

### 1. Schechter & Taylor 1899 (MSS A and B)
See [`schechter_1899/`](schechter_1899/). Public-domain scholarly
edition with Schechter's printed Hebrew transcription and facsimile
plates of MSS A and B. This covers the first Genizah manuscripts
discovered (about half of the total recovered Hebrew Sirach). Already
downloaded and vendored here.

### 2. Fresh AI-vision transcription from public-domain photographs
See [`genizah_photos/`](genizah_photos/). For manuscripts and folios
not covered by Schechter 1899 (MSS C, D, E, F, additional B folios),
we produce our own transcription from:
- Cambridge Digital Library (cudl.lib.cam.ac.uk) — Taylor-Schechter
  collection images. License terms vary per item; we use only those
  with permissive research+redistribution terms or request explicit
  permission where needed.
- Oxford Bodleian public-domain imagery.
- JTS New York and BnF Paris for their respective holdings.
- Friedberg Genizah Project (genizah.org) — images require
  registration; we do not vendor their files. Citations only.

Provenance for each transcribed folio is recorded in
`genizah_photos/PROVENANCE.md` as pages are processed.

### 3. Masada scroll (deferred)
See [`masada/`](masada/). The Masada Ben Sira scroll photographs are
currently hosted by the **Israel Antiquities Authority Leon Levy Dead
Sea Scrolls Digital Library** under a restrictive license
(`© 2026 IAA — reproduction prohibited without written permission`).

We have drafted a formal licensing request to the IAA (see
`masada/IAA_LICENSING_REQUEST.md`). Pending their response, Masada
Sirach remains **blocked for direct inclusion** in COB. This affects
approximately Sirach 39:27–43:30.

In the interim we use Schechter-era transcription for sections where
MS B overlaps with the Masada scroll, and clearly annotate the
transcription gap where it does not.

## What this gives us

| Sirach section | Primary Hebrew witness we can use | Status |
|---|---|---|
| 3:6 – 16:26 (approx.) | MS A (Schechter 1899) | Public domain, vendored |
| 30:11 – 33:3, 35:11 – 38:27, 39:15 – 51:30 | MS B (Schechter 1899 + later publications) | Public domain, vendored where 1899 covers |
| 4:23 – 5:13, 6:5 – 37, 18:31 – 19:3, 20:5 – 7, 25:8 – 26:2 | MS C | Via later PD publications — to verify |
| 51:13 – 30 | MS E | Via Marcus 1931 and later (PD) |
| 39:27 – 43:30 | Masada scroll | **Blocked on IAA licensing** |
| 6:14–15, 6:20–31 | Qumran 2Q18 / 11QPsa | **Blocked on IAA licensing** |

The approximately one-third of Sirach where no Hebrew survives (chapters
1–2, parts of 16–30, chapters 44–51 except what MSS B and E cover) will
be translated from the Greek (Swete LXX), clearly marked.

## Methodology

Every verse of Sirach in COB will declare its primary-source witness
in the per-verse YAML:

```yaml
source:
  edition: Hebrew Sirach MS A (Schechter 1899)
  text: "…Hebrew text…"
  greek_parallel: "…LXX Greek for comparison…"
```

Where the Hebrew and Greek diverge materially, both readings are
preserved: Hebrew in the main `source.text` field, Greek in
`source.greek_parallel`, and a footnote on the English translation
flags the divergence.

This is more rigorous than what any existing modern English Bible
does for Sirach and is one of the reasons Phase 2 of the
deuterocanonical work is worth the effort.
