# Jubilees Charles 1895 body-extent audit (2026-04-22)

## Core finding

The earlier assumption that the Ge'ez body ended at PDF **page 210** was
wrong.

Additional probing eventually showed the Charles 1895 Ge'ez body continues to
PDF **page 267**.

## Evidence

### 1. Running-head evidence from later pages

Later rendered pages clearly show Ge'ez body text plus Roman chapter running
heads:

- PDF **p220** → running head around **chapters 34–35**
- PDF **p230** → **chapter 38**
- PDF **p250** → **chapter 45**
- PDF **p260** → **chapter 49**
- PDF **p264** → still **chapter 49** (`XLIX. 16-23`)
- PDF **p266** → **chapter 50** (`L. 1-9`)
- PDF **p267** → **chapter 50** continuation (`L. 10-13`)

Pages **268+** sampled as non-Ge'ez / appendix material, indicating the Ge'ez
body ends with chapter 50 at **p267**.

### 2. Vertex chapter-detection evidence

Using Vertex AI Gemini (service-account / "second key" path), full chapter
classification over pages 37–267 recovered a coherent late-book spine:

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
- ch50 → p266

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

- PDF pages **37–267**

That means the regenerated Charles 1895 body is no longer just the earlier
37–210 slice, nor the later intermediate 37–264 assumption.

## Vertex status

The repo's Ethiopic OCR / detection path was updated to support **Vertex AI
Gemini** directly.

Confirmed working with the service-account credential path (`/cartha/openclaw/gemini_api_key_2`):

- page OCR via `tools/ethiopic/ocr_geez.py --backend vertex`
- parallel OCR via `tools/ethiopic/run_parallel_ocr.py --backend vertex`
- chapter detection via `tools/jubilees/detect_chapters.py --backend vertex`

## Chapter-map status after correction

Chapter 50 is now located.

Current practical state:

- **50/50 chapters recovered** in the proposed page map
- the trusted Ge'ez body appears to run through **p267**
- pages **268+** appear to be post-body appendix / non-Ge'ez material

## Practical consequence for production

The post-OCR path is now clearer:

1. finalize the corrected Ge'ez body extent (37–267)
2. finish the trusted chapter page map (now effectively recovered through all
   50 chapters)
3. continue generalizing the Jubilees verse parser for later-page line-start
   verse numbering and mid-page chapter transitions
4. improve / validate the full corpus build
So the blocker after OCR is now **verse segmentation quality**, not OCR
availability or source-boundary clarity.
