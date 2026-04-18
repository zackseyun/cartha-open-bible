# Translation

This directory contains the per-verse YAML files for the Cartha Open Bible.

## Layout

```
translation/
├── nt/                       New Testament
│   ├── matthew/
│   │   ├── 01/
│   │   │   ├── 001.yaml      Matthew 1:1
│   │   │   ├── 002.yaml      Matthew 1:2
│   │   │   └── ...
│   │   └── ...
│   ├── mark/
│   ├── ...
│   └── revelation/
└── ot/                       Old Testament
    ├── genesis/
    ├── ...
    └── malachi/
```

Book names follow full English conventional form (lowercase, underscores
for spaces — e.g., `1_samuel`, `song_of_songs`).

Chapters are zero-padded 3-digit directories. Verses are zero-padded
3-digit YAML files. The padding keeps alphabetical sorts aligned with
numerical order.

## File format

Each YAML file conforms to `/schema/verse.schema.json`. See that file
for the full specification. See `METHODOLOGY.md` for the pipeline that
produces these files.

A minimal valid verse record:

```yaml
id: PHP.1.1
reference: "Philippians 1:1"
source:
  edition: SBLGNT
  text: "Παῦλος καὶ Τιμόθεος..."
translation:
  text: "Paul and Timothy..."
  philosophy: optimal-equivalence
ai_draft:
  model_id: gpt-5.4
  model_version: "gpt-5.4"
  prompt_id: nt_draft_v1
  prompt_sha256: "..."
  timestamp: "2026-04-17T21:31:58Z"
  output_hash: "..."
status: draft
```

## Status

Every verse currently in this directory is an AI-drafted rendering,
released openly with full rationale alongside it. Track progress via the
CHANGELOG.
