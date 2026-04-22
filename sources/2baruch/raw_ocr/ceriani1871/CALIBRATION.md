# Ceriani 1871 — initial 5-page OCR calibration

Date: **2026-04-21**
Backend: **Gemini 3.1 Pro preview**
Pipeline: [`../../../../tools/2baruch/ocr_pipeline.py`](../../../../tools/2baruch/ocr_pipeline.py)
Layout mode: **ceriani_region_assembled**

## Pages

| PDF page | TXT | Meta | Output chars | Duration (s) |
|---:|---|---|---:|---:|
| 187 | `ceriani1871_p0187.txt` | `ceriani1871_p0187.meta.json` | 1429 | 175.98 |
| 190 | `ceriani1871_p0190.txt` | `ceriani1871_p0190.meta.json` | 1503 | 166.09 |
| 195 | `ceriani1871_p0195.txt` | `ceriani1871_p0195.meta.json` | 1393 | 178.73 |
| 205 | `ceriani1871_p0205.txt` | `ceriani1871_p0205.meta.json` | 1502 | 217.12 |
| 220 | `ceriani1871_p0220.txt` | `ceriani1871_p0220.meta.json` | 1386 | 273.26 |

## Main decision

A naive whole-page OCR attempt on Ceriani page 190 under-transcribed the
layout. The current pipeline therefore slices each page into:

1. running head
2. Syriac column 1
3. Syriac column 2
4. apparatus column 1
5. apparatus column 2

and then assembles the final page file with the normal page markers.

A follow-up refinement kept the main Syriac columns on the stable full-crop path,
but **content-trimmed the lower apparatus crops only** before OCR. That materially
improved noisy lower-apparatus output (especially page 220 right apparatus) without
reintroducing column-level regressions.

## Notes

- The calibration output is good enough to prove the Ceriani layout and
  provenance path work.
- Some lower-apparatus lines remain noisy and will need cleanup or more
  targeted prompting in later passes.
- Natural next step: add another Ceriani batch plus a small Kmosko
  control batch for witness comparison.
