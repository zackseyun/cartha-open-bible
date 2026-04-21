# 1 Enoch chapter 1 — OCR method comparison (Charles 1906 p.40)

## Methods tested against the same scan-truth set (verses 1–5)

| Method | Accuracy | Notes |
|---|---:|---|
| Full-page OCR | **63.07%** | Best of the tested methods so far |
| Apparatus-masked body-only OCR | **60.27%** | Slightly worse than baseline, but better than the coarse segmented pass |
| Segmented bands (`bands_v1`) | **57.54%** | Coarse bands did not help |
| Automatic line-region OCR | **20.85%** | Very poor; current line-by-line approach is not usable |

## Practical reading of the result

- The old Beta maṣāḥǝft comparison overstated failure because it mixed in edition variance.
- But once we switched to scan-grounded truth, the rescue experiments still did **not** beat the plain full-page baseline.
- Apparatus masking is the closest alternative, but it still trails the baseline.
- Automatic line-region OCR is currently much worse than all other methods.

## Current decision

For now, **full-page OCR remains the best-performing method among the tested variants**.

That does **not** mean it is good enough for bulk Ethiopic OCR yet — only that the tested rescue methods did not improve it.

## If work continues from here

The next promising direction is probably **not** more coarse segmentation. Better candidates would be:

1. consensus / multi-run reconciliation on the same page,
2. specialized masking of superscript note markers before OCR,
3. fine-grained line detection tied to explicit verse-start anchors,
4. a second model used as a checker rather than as a parallel OCR source.
