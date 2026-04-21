# Gospel of Thomas — Phase E overview prompt

You are preparing an accuracy-first English translation workflow for **Gospel of Thomas**.
Goal: Accuracy-first translation prep with Coptic primary, Greek overlap, and Synoptic parallel awareness.

## Witness posture

- **mattison_zinner_coptic** (primary_coptic) — fetched; source: https://gospels.net/thomas
- **gebhardt_klein_2024_coptic** (cross_check_coptic) — pending_input; source: local source pending
- **poxy654_greek** (greek_overlap_witness) — fetched; source: http://www.agraphos.com/thomas/greek/poxy654/
- **poxy1_greek** (greek_overlap_witness) — fetched; source: http://www.agraphos.com/thomas/greek/poxy1/
- **poxy655_greek** (greek_overlap_witness) — fetched; source: http://www.agraphos.com/thomas/greek/poxy655/

## Guardrails

- If a Greek fragment overlaps a saying and differs meaningfully from the Coptic, record both readings and defend the decision.
- Treat Synoptic parallels as context, not as pressure to harmonize Thomas into the canonical gospels.
- Keep odd or sharp Thomasine diction when the witness supports it instead of smoothing it into familiar church English.

## Translation stance

- Translate from the Coptic witness first.
- If a Greek overlap witness exists for this unit, compare it and record meaningful divergences instead of silently collapsing them.
- When a Synoptic parallel exists, use it as context only; keep Thomas sounding like Thomas unless the source evidence justifies a closer echo.
- Flag any place where the Coptic and Greek appear to point in different directions.

## Consult-only references

- **Layton NHS 20** — Consult for Thomas on difficult Coptic readings; do not copy phrasing.
- **Plisch 2008** — Secondary Thomas consultation layer for knotty logia.
- **DeConick 2007** — Consult on Thomas interpretation and saying-level decisions.
- **Meyer 2007** — Readable consultation layer, especially for Thomas and Truth.

## Required output for each unit

- translation draft
- textual note
- Greek-overlap decision note (if applicable)
- revision risk note

## Current scaffold status

- Register OCR input for gebhardt_klein_2024_coptic
