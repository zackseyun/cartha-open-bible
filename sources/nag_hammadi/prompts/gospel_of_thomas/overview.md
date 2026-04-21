# Gospel of Thomas — Phase E overview prompt

You are preparing an accuracy-first English translation workflow for **Gospel of Thomas**.
Goal: Accuracy-first translation prep with Coptic primary, Greek overlap, and Synoptic parallel awareness.

## Witness posture

- **mattison_zinner_coptic** (primary_coptic) — fetched; source: sources/nag_hammadi/raw/gospel_of_thomas/mattison_zinner_coptic.txt
- **gebhardt_klein_2024_coptic** (cross_check_coptic) — pending_input; source: local source pending
- **grondin_interlinear_2002** (cross_check_coptic) — queued; source: sources/nag_hammadi/staging/gospel_of_thomas/grondin_interlinear_2002/gtbypage_112702.pdf
- **poxy654_greek** (greek_overlap_witness) — fetched (Sayings 1–7); source: sources/nag_hammadi/raw/gospel_of_thomas/poxy654_greek.txt
- **poxy1_greek** (greek_overlap_witness) — fetched (Sayings 26–33); source: sources/nag_hammadi/raw/gospel_of_thomas/poxy1_greek.txt
- **poxy655_greek** (greek_overlap_witness) — fetched (Sayings 24 and 36–39); source: sources/nag_hammadi/raw/gospel_of_thomas/poxy655_greek.txt

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
