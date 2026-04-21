# 1 Enoch chapter 1 — superscript-masked rollout

## What changed
- Applied `--preprocess mask_superscripts` to the live Charles 1906 chapter-1 OCR run.
- Rebuilt page outputs and chapter text for pages **40** and **42**.

## Before vs after
- Chapter text similarity (old vs new): **38.12%**
- Old chapter chars: **947**
- New chapter chars: **1071**
- Old page count: **2**
- New page count: **2**
- New preprocess flag: **mask_superscripts**

## Current scan-truth score
- Charles p40 against scan-truth (vv. 1–5): **67.33%**

## Decision
This masked-superscript rollout is now the active Charles chapter-1 OCR baseline.
