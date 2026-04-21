# 1 Enoch chapter 1 — OCR method comparison (Charles 1906 p.40)

## Methods tested against the same scan-truth set (verses 1–5)

| Method | Accuracy | Notes |
|---|---:|---|
| Full-page OCR (original baseline) | **63.07%** | Previous best baseline |
| Full-page OCR, temperature 0 | **54.02%** | More repeatable, but clearly worse |
| 3-run consensus sample (best single sampled run) | **59.30%** | Did not beat the original baseline |
| 3-run consensus sample (medoid run) | **55.28%** | Stable-ish center run, but worse than baseline |
| Apparatus-masked body-only OCR | **60.27%** | Better than coarse segmentation, but below baseline |
| Segmented bands (`bands_v1`) | **57.54%** | Coarse bands did not help |
| Automatic line-region OCR | **20.85%** | Not usable in current form |
| Masked superscripts (run 1) | **67.69%** | **Current best tested method** |
| Masked superscripts (run 2) | **66.10%** | Also beats the old full-page baseline |

## Practical reading of the result

- The old Beta maṣāḥǝft comparison overstated OCR failure because it mixed in edition variance.
- Deterministic full-page OCR did not help; it reduced accuracy.
- A small 3-run consensus sweep also did not beat the original baseline.
- The strongest improvement so far comes from **masking tiny superscript note markers inside the body text before OCR**.
- Apparatus masking alone helps less than superscript masking.
- Coarse segmentation and automatic line-region OCR both underperform.

## Current decision

**Best current direction: superscript-masked full-page OCR.**

It is still not perfect, and reruns are not perfectly identical, but it is the best-performing approach we have measured so far.

## If work continues from here

The next promising direction is probably:

1. apply superscript masking by default to Charles-style Ethiopic pages,
2. combine superscript masking with light apparatus masking if needed,
3. use extra Gemini capacity only if we want a larger consensus / re-ranking sweep after masking.
