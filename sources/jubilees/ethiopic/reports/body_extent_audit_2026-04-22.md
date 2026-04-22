# Jubilees Charles 1895 body-extent audit (2026-04-22)

## Core finding

The earlier assumption that the Ge'ez body ended at PDF **page 210** was
wrong.

Additional probing showed the Charles 1895 Ge'ez body continues at least to
PDF **page 264**.

## Evidence

### 1. Running-head evidence from later pages

Later rendered pages clearly show Ge'ez body text plus Roman chapter running
heads:

- PDF **p220** → running head around **chapters 34–35**
- PDF **p230** → **chapter 38**
- PDF **p250** → **chapter 45**
- PDF **p260** → **chapter 49**
- PDF **p264** → still **chapter 49** (`XLIX. 16-23`)

Pages **265+** sampled as non-Ge'ez, indicating the Ge'ez body likely ends at
or just before **264**.

### 2. Vertex chapter-detection evidence

Using Vertex AI Gemini (service-account / "second key" path), full chapter
classification over pages 37–264 recovered a coherent late-book spine:

- ch33 → p214
- ch34 → p218
- ch35 → p220
- ch36 → p224
- ch37 → p226
- ch38 → p230
- ch39 → p232
- ch45 → p250
- ch46 → p252
- ch47 → p254
- ch48 → p256
- ch49 → p260

### 3. Manual running-head recovery filled additional gaps

Manual head inspection recovered otherwise-missed starts:

- ch10 → p108
- ch12 → p114
- ch26 → p166
- ch40 → p236
- ch41 → p238
- ch42 → p242
- ch43 → p245
- ch44 → p247

These are recorded in:

- `sources/jubilees/ethiopic/chapter_detection/charles_1895_manual_starts.json`

## OCR status after correction

The body OCR now covers:

- PDF pages **37–264**

That means the regenerated Charles 1895 body is no longer just the earlier
37–210 slice.

## Vertex status

The repo's Ethiopic OCR / detection path was updated to support **Vertex AI
Gemini** directly.

Confirmed working with the service-account credential path (`/cartha/openclaw/gemini_api_key_2`):

- page OCR via `tools/ethiopic/ocr_geez.py --backend vertex`
- parallel OCR via `tools/ethiopic/run_parallel_ocr.py --backend vertex`
- chapter detection via `tools/jubilees/detect_chapters.py --backend vertex`

## Remaining unresolved issue

Only **chapter 50** remains unlocated in the Ge'ez body.

Given that:

- p260 is chapter 49,
- p264 is still chapter 49,
- sampled pages 265+ are non-Ge'ez,

there are two live possibilities:

1. the vendored PDF's Ge'ez section ends before chapter 50, or
2. chapter 50 is present but not yet isolated because of section-boundary
   complexity near the end.

This requires a short focused source audit.

## Practical consequence for production

The post-OCR path is now clearer:

1. finalize the corrected Ge'ez body extent (37–264)
2. finish the trusted chapter page map (49 chapters recovered, ch50 pending)
3. continue generalizing the Jubilees verse parser for later-page Arabic
   verse numbering and mid-page chapter transitions
4. only then promote the full corpus build

So the blocker after OCR is **chapter segmentation + final source-boundary
clarity**, not OCR availability.
