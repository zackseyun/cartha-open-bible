# Jubilees full-body OCR rerun — Charles 1895 (2026-04-22)

## Outcome

- **Full Charles 1895 Ge'ez body OCR regenerated successfully**:
  PDF pages **37-210** → `sources/jubilees/ethiopic/transcribed/charles_1895/body/`
- Total body pages regenerated: **174 / 174**
- Engine: **Gemini 3.1 Pro preview**, plaintext OCR
- Execution pattern: **2 workers** on the working API key

This closes the immediate “missing body/ directory” blocker that had
left Jubilees unable to move beyond chapter 1 pilot work.

## Important operational findings

### 1. The parallel runner is now production-useful

The new shared runner:

- `tools/ethiopic/run_parallel_ocr.py`

successfully drove the full 174-page rerun.

### 2. Resume semantics had a real bug, now fixed

Earlier, failed OCR attempts still wrote an empty `.txt` plus `.json`
metadata, and `--resume` treated those pages as already complete. That
would have silently stranded failed pages in any long run.

This is now fixed in:

- `tools/ethiopic/ocr_geez.py`
- `tools/ethiopic/run_parallel_ocr.py`

Only prior outputs with non-empty text and no recorded error are now
treated as resumable successes.

### 3. Only one Gemini key is usable right now

The secret `/cartha/openclaw/gemini_api_key` contains two API keys, but
in practice:

- **key #1**: usable
- **key #2**: quota-exhausted / unusable during this rerun

So the successful full-body rerun used **key #1 only**, with two workers
concurrently on that single functioning key.

### 4. Tiny OCR pages are often legitimate, not necessarily failures

A quick low-char audit found **16** very short OCR pages (`< 80 chars`).
These are not automatically bad pages. Example:

- **PDF p41** rendered visually and confirmed to be mostly running head +
  Greek/apparatus material, so the OCR output of just
  `መጽሐፈ፡ ኩፋሌ፡` is correct under our “skip English/Latin apparatus”
  prompt policy.

Several other short pages likely fall into the same category.

## Chapter-mapping follow-up

### Local OCR-native detector

Implemented:

- `tools/jubilees/detect_chapters_from_ocr.py`

This detector scans the OCR text itself for likely chapter-start markers
and writes a cache compatible with:

- `tools/jubilees/build_page_map.py`

Current result on the full regenerated body:

- detected starts for **20** chapters automatically
- reliable through the early portion of the book
- **not yet strong enough to promote as the final page map**

Why not promoted yet:

- later-book detection clearly drifts
- chapter numerals and verse numerals can still be confused in some
  contexts
- additional heuristics or spot-confirmation are still needed before
  trusting all 50 chapters

### AI spot-check on narrowed candidates

To conserve the remaining daily request budget on key #1, the full-image
Gemini chapter detector was *not* run across all 174 pages after OCR
completed.

Instead, AI classification was used only on a narrowed candidate set of
likely chapter-start pages. This produced some useful confirmations
(e.g. early chapters plus later anchors like chapter 24 and chapter 30),
but not enough to complete the full page map.

## Practical state at end of rerun

### Done

- full Charles 1895 body OCR
- parallel OCR runner
- resume-bug fix
- OCR-native chapter detector
- page-map builder tooling
- corpus builder tooling
- prompt-builder hardening for partial-body fallback

### Not done yet

- final trusted per-chapter page map for all 50 chapters
- full `JUBILEES.jsonl` corpus build from a finished page map

## Recommended next step

With the body OCR now safely regenerated, the best next session is:

1. finish the remaining chapter-map logic / confirmation
2. promote `sources/jubilees/page_map.json`
3. run `tools/jubilees/build_corpus.py`
4. use the already-built Jubilees prompt builder against the full body

That means Jubilees is now blocked mainly on **chapter segmentation
quality**, not on OCR infrastructure or missing text.
