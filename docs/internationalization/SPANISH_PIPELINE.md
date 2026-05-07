# Spanish source-grounded POB pipeline

This pipeline is intentionally **not** a simple English-to-Spanish localization. It drafts Spanish from the original source payload while using the existing English POB text, lexical decisions, theological decisions, footnotes, revisions, and review summaries as audit context.

## Output layout

Spanish records mirror the English source tree under:

```text
translation_es/<testament>/<book>/<chapter>/<verse>.yaml
```

Each record stores:

- `source` copied from the English POB record
- `base_translation` with the English YAML path and current English text
- `translation.language: es` and `translation.text` plus Spanish footnotes
- Spanish `lexical_decisions` and `theological_decisions`
- `ai_draft.usage.estimated_cost_usd`
- `source_grounding.english_pob_role: consult_only`
- optional `review_pass` after review

## Commands

Estimate draft cost:

```bash
python3 tools/spanish_pipeline.py estimate --limit 250 --model gpt-5.4-mini
```

Draft a pilot batch:

```bash
python3 tools/spanish_pipeline.py draft --book john --limit 5 \
  --model gpt-5.4-mini \
  --deployment "$AZURE_OPENAI_MINI_DEPLOYMENT_ID"
```

Review a pilot batch:

```bash
python3 tools/spanish_pipeline.py review --book john --limit 5 --apply-revisions \
  --model gpt-5.4 \
  --deployment "$AZURE_OPENAI_REVIEW_DEPLOYMENT_ID"
```

Summarize progress and observed costs:

```bash
python3 tools/spanish_pipeline.py summary
```

Validate existing Spanish records:

```bash
python3 tools/spanish_pipeline.py validate --only-existing
```

## Scale-out pattern

The script supports sharding for parallel workers:

```bash
python3 tools/spanish_pipeline.py draft --limit 0 --shard-count 8 --shard-index 0 --keep-going
python3 tools/spanish_pipeline.py draft --limit 0 --shard-count 8 --shard-index 1 --keep-going
# ...
```

Use a conservative shard count until Azure rate limits are measured. Each output path uses a lock file to avoid duplicate writes.

## Model balance

Recommended balanced path:

1. Bulk Spanish draft with `gpt-5.4-mini`.
2. Review all records, or at least all high-risk records, with `gpt-5.4` or a mixed mini/full policy.
3. Treat `spanish_needs_adjudication` as the queue for full GPT-5.4 source-facing adjudication before publication.
4. Inspect `ai_draft.usage` and `review_pass.usage` to reconcile actual Azure spend after each batch.
