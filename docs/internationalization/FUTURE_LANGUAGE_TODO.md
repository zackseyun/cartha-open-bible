# Future Language Roadmap: Portuguese + Chinese

After the Spanish pipeline is stable, Portuguese and Chinese are the next practical expansion targets. Keep this work deliberately incremental: copy the Spanish process, change only the language-specific decisions, and validate with small book/chapter pilots before scaling.

## Shared prerequisites

- Reuse the Spanish runbook structure: source selection, glossary, style guide, pilot batch, review pass, publish/export checks, and rollback notes.
- Confirm the translation pipeline can parameterize locale, glossary, prompts, validation rules, and output paths without Spanish-specific assumptions.
- Add language-specific smoke tests for verse counts, chapter ordering, punctuation, Unicode handling, and mobile/web rendering.
- Define a reviewer loop before broad generation: one short Gospel sample, one Psalm/proverb sample, and one extra-canonical prose sample if applicable.
- Keep provenance and audit artifacts consistent with Spanish so later languages can be compared apples-to-apples.

## Portuguese choice points

- Decide primary locale first:
  - pt-BR is likely the default if optimizing for audience size and modern digital usage.
  - pt-PT may need a separate pass if European Portuguese tone, grammar, and ecclesial terminology matter.
- Avoid mixing Brazilian and European forms inside one edition. Track spelling, second-person usage, and idioms explicitly in the style guide.
- Build a Portuguese glossary from the Spanish decisions where possible, but re-check theological terms directly instead of translating Spanish mechanically.
- Pilot with pt-BR first unless there is a clear product reason to prioritize pt-PT.

## Chinese choice points

- Decide script/locale first:
  - Simplified Chinese is likely the initial broad-reach edition.
  - Traditional Chinese may need a separate edition for Taiwan/Hong Kong/community expectations.
- Lock terminology early. Chinese biblical/theological terms can vary significantly by tradition and region.
- Include rules for names, book titles, divine titles, punctuation, quotation marks, and whether to preserve or adapt transliterated terms.
- Validate rendering carefully: line breaks, punctuation width, search indexing, copy/paste behavior, and mobile font fallback.
- Consider a glossary-first pilot before full chapter generation because terminology drift is the highest risk.

## Copy from the Spanish run

- Prompt scaffolding and batch orchestration.
- Glossary/style-guide template.
- Pilot selection and review rubric.
- Verse/chapter validation scripts and publish checks.
- Export manifest updates, CDN/mobile/web smoke checks, and rollback checklist.

## Suggested order

1. Finish and freeze the Spanish runbook artifacts.
2. Fork the Spanish docs into Portuguese and Chinese templates.
3. Run a small pt-BR pilot, review, then scale if clean.
4. Run a Simplified Chinese glossary + pilot, review terminology, then scale carefully.
5. Revisit pt-PT and Traditional Chinese once the primary editions are stable.
