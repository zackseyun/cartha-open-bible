# Tools

Python scripts for drafting, cross-checking, verifying, and linting the
Cartha Open Bible.

## Scripts

| Script | Status | Purpose |
|---|---|---|
| `sblgnt.py` | implemented | Parses the MorphGNT SBLGNT text files; exposes `load_verse(book, chapter, verse)` and `morphology_lines(verse)`. |
| `wlc.py` | implemented | Parses the Westminster Leningrad Codex / unfoldingWord Hebrew Bible for OT verses. |
| `draft.py` | implemented | Produces an AI-drafted verse YAML for a single verse. Reads source text, extracts relevant DOCTRINE.md sections, calls a frontier LLM with a tool definition enforcing structured output, writes a schema-valid YAML to `translation/<testament>/<book>/<chapter>/<verse>.yaml`. Supports `--dry-run` for prompt inspection without an API call. |
| `cross_check.py` | stub | Runs draft against Claude + GPT + Gemini in parallel, scores agreement, surfaces divergences. Spec in METHODOLOGY.md Stage 3. |
| `verify.py` | not yet written | Re-runs the documented pipeline for a published verse. Confirms AI draft reproduces and cross-check reproduces. |
| `consistency_lint.py` | implemented | Checks internal consistency across drafted YAMLs. Flags undocumented lexical variance, contested-term doctrine gaps/overrides, and empty source text; writes Markdown reports to `lint_reports/`. |
| `run_phase.py` | implemented | Drives a full phase (e.g., Phase 0 = Philippians) end to end: drafting, linting, commits, and CHANGELOG updates. |
| `chapter_queue.py` | implemented | Maintains a SQLite-backed chapter queue/ledger for whole-Bible drafting. |
| `chapter_worker.py` | implemented | Claims chapter jobs from the queue, drafts them in a worker worktree, and commits chapter-sized results. |
| `chapter_merge.py` | implemented | Cherry-picks completed worker chapter commits onto `main` in canonical order and records merge state. |
| `dashboard_server.py` | implemented | Serves a local live dashboard showing active queue workers, claimed chapters, progress percentages, ready-to-merge jobs, and recent commits. |
| `transcribe_source.py` | implemented | Transcribes Swete Greek and Schechter Hebrew source pages from archival scans via Azure GPT-5.4 vision, writing UTF-8 text plus provenance sidecars. |
| `review_transcription.py` | implemented | Reviews an existing Swete transcription against the scan image via Azure GPT-5.4, returning structured corrections-only function output and per-page review metadata. |
| `summarize_transcription_reviews.py` | implemented | Aggregates Azure and Claude review outputs, reports parseability, correction counts, and high-risk pages for adjudication. |
| `review_phase8_swete.sh` | implemented | Convenience launcher for the full 572-page Phase 8 Swete Azure review run, with resumable `--skip-existing` behavior and per-volume logs. |

## Prerequisites

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt
```

Required environment variables:

```
ANTHROPIC_API_KEY=...    # for Claude drafts / cross-check
OPENAI_API_KEY=...       # for GPT drafts / cross-check
OPENROUTER_API_KEY=...   # for OpenRouter GPT drafts
AZURE_OPENAI_ENDPOINT=... # for Azure OpenAI GPT drafts
AZURE_OPENAI_API_KEY=...  # for Azure OpenAI GPT drafts
AZURE_OPENAI_DEPLOYMENT_ID=... # optional, defaults to gpt-5-4-deployment
GOOGLE_API_KEY=...       # for Gemini cross-check
```

## Quick start — draft one verse

```bash
# Dry run: inspect the prompt that would be sent, without an API call.
python3 tools/draft.py --ref "Philippians 1:1" --dry-run

# Real run via OpenRouter GPT-5.4:
export OPENROUTER_API_KEY=...
python3 tools/draft.py --ref "Philippians 1:1" --backend openrouter-sdk --model openai/gpt-5.4

# Real run via Azure OpenAI GPT-5.4:
export AZURE_OPENAI_ENDPOINT=...
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_DEPLOYMENT_ID=gpt-5-4-deployment
python3 tools/draft.py --ref "Philippians 1:1" --backend azure-openai --model gpt-5.4
```


# Local worker dashboard:
python3 tools/dashboard_server.py --host 127.0.0.1 --port 8765

Model, temperature, and prompt ID are configurable via CLI flags or
environment variables (`CARTHA_MODEL_ID`, `CARTHA_TEMPERATURE`,
`CARTHA_PROMPT_ID`).
