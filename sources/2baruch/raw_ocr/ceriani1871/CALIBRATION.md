# Ceriani 1871 — initial 5-page OCR calibration

Date: **2026-04-21**
Backend: **Gemini 3.1 Pro preview**
Pipeline: [`../../../../tools/2baruch/ocr_pipeline.py`](../../../../tools/2baruch/ocr_pipeline.py)
Layout mode: **ceriani_region_assembled**

## Pages

| PDF page | TXT | Meta | Output chars | Duration (s) |
|---:|---|---|---:|---:|
| 187 | `ceriani1871_p0187.txt` | `ceriani1871_p0187.meta.json` | 1417 | 167.43 |
| 190 | `ceriani1871_p0190.txt` | `ceriani1871_p0190.meta.json` | 1504 | 140.93 |
| 195 | `ceriani1871_p0195.txt` | `ceriani1871_p0195.meta.json` | 1359 | 176.54 |
| 205 | `ceriani1871_p0205.txt` | `ceriani1871_p0205.meta.json` | 1479 | 240.53 |
| 220 | `ceriani1871_p0220.txt` | `ceriani1871_p0220.meta.json` | 1217 | 184.36 |

## Main decision

A naive whole-page OCR attempt on Ceriani page 190 under-transcribed the
layout. The current pipeline therefore slices each page into:

1. running head
2. Syriac column 1
3. Syriac column 2
4. apparatus column 1
5. apparatus column 2

and then assembles the final page file with the normal page markers.

## Notes

- The calibration output is good enough to prove the Ceriani layout and
  provenance path work.
- Some lower-apparatus lines remain noisy and will need cleanup or more
  targeted prompting in later passes.
- Natural next step: add another Ceriani batch plus a small Kmosko
  control batch for witness comparison.
