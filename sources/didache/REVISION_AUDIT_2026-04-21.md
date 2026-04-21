# Didache revision / audit pass — 2026-04-21

## What was done

This pass moved the Didache from **first-pass draft** to **reviewed
first-pass draft**.

Three layers were involved:

1. **Primary source** — normalized Hitchcock & Brown 1884 Greek
2. **Secondary cross-check** — Schaff 1885 chapter extracts from the
   Internet Archive DjVu XML
3. **Independent reviewer** — Gemini 2.5 Pro via
   `tools/review_didache.py`

## Artifacts added

- `tools/didache_secondary.py`
- `tools/review_didache.py`
- `sources/didache/secondary/schaff_1885/chapter_map.json`
- `sources/didache/secondary/schaff_1885/chapters/ch01.txt` …
  `ch16.txt`

The Gemini review JSON/meta outputs were written under the local
ignored path `state/reviews/didache/` and therefore are not committed,
but every Didache chapter YAML now carries `review_passes` metadata.

## Coverage

All **16 Didache chapters** were reviewed.

- `translation/extra_canonical/didache/001.yaml`
- …
- `translation/extra_canonical/didache/016.yaml`

## What the review focused on

- source drift from the Greek
- flattened liturgical or moral language
- weak lexical decisions
- careless or under-specified footnotes
- difficult clauses where a secondary witness might clarify the reading

## Notable outcomes

- The secondary Schaff witness is now available chapter-by-chapter for
  future audit work.
- The full Didache draft has passed through an independent Gemini Pro
  review layer after the original GPT-5.4 drafting pass.
- A few stylistic and lexical adjustments were made across the book to
  tighten fidelity and preserve the sharper early-Christian register.
- Review-time footnote marker noise introduced in a handful of chapters
  was cleaned back out before finalizing the pass.

## Remaining risks

This is still a **reviewed first-pass draft**, not a final critical
edition.

The biggest remaining risks are:

- places where the normalized Hitchcock source itself may need finer
  editorial cleanup
- chapters whose Greek contains awkward or textually difficult clauses
  (especially 7, 12, 13, 16)
- eventual full comparison against additional Didache editions beyond
  Hitchcock + Schaff

## Next natural step

If Didache is revisited again, the next layer should be a **targeted
manual editorial pass** on the trickiest clauses, not another broad
first-pass model sweep.
