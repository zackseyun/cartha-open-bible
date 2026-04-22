# Gospel of Thomas — Phase E overview prompt

You are preparing an accuracy-first Coptic-grounded English translation of the
Gospel of Thomas from the **Paul Dilley, 2025 (Coptic Scriptorium v6.2.0)** (CC-BY 4.0).

## Primary witness

- **coptic_scriptorium_thomas_dilley_2025** — Paul Dilley, 2025 (Coptic Scriptorium v6.2.0), license CC-BY 4.0.
- Source: Nag Hammadi Codex II (NHAM 02), pp. 32–51. URN: `urn:cts:copticLit:nh.thomas.NHAM02:0-114`.
- Parsed text: `sources/nag_hammadi/texts/gospel_of_thomas/coptic.jsonl`.

## Scope

- 116 segments: incipit + 114 sayings + subtitle (per TEI `div1` units).

## Consult-only references

- Layton NHS 20 (1989), Bethge et al. 1996, Plisch 2008, DeConick 2007, Meyer 2007.
- Mattison/Zinner OGV — English comprehension cross-check only.

## Guardrails

- If a Greek fragment overlaps a saying and differs meaningfully from the Coptic, record both readings and defend the decision.
- Treat Synoptic parallels as context, not as pressure to harmonize Thomas into the canonical gospels.
- Keep odd or sharp Thomasine diction when the witness supports it instead of smoothing it into familiar church English.
- The Coptic has Lycopolitan features in a mostly Sahidic base — where the dialect interacts with meaning, note it instead of flattening it to standard Sahidic.

## Required output per saying

- translation draft
- textual note
- Greek-overlap decision note (if applicable)
- Synoptic-parallel check (if any)
- revision risk note
