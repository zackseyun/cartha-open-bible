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
  model_id: claude-opus-4-7
  model_version: "2026-01-15"
  prompt_id: nt_draft_v3
  prompt_sha256: "..."
  timestamp: "2026-04-16T14:23:00Z"
  output_hash: "..."
human_review:
  status: approved
  reviewers:
    - name: "Zack Yun"
      credentials: "Founder, Cartha Inc."
      signed_at: "2026-04-18T10:00:00Z"
      signature: "ed25519:..."
```

## Status

This directory is empty pending:
1. Completion of the draft pipeline (`tools/draft.py`)
2. Vendoring of SBLGNT and WLC/UHB source texts
3. Generation of keypairs for the initial review board
4. First pilot book draft

Track progress via the project's task list and CHANGELOG.
