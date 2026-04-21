# Cartha Open Bible — Queue Workflow

This workflow turns the Bible drafting run into a real chapter queue instead of an ad-hoc collection of shell sessions.

## Why this exists

The project is now large enough that the main risks are operational:
- workers overlap,
- partial chapters get stranded,
- chapter progress is hard to audit,
- pushing and merging becomes noisy,
- and recovery after a failure is too manual.

The queue system fixes that by making **chapter** the atomic job.

## Core pieces

### `tools/chapter_queue.py`
Maintains a SQLite queue in `state/chapter_queue.sqlite3`.

Each chapter job tracks:
- phase
- book
- chapter
- verse count
- status (`pending`, `running`, `completed`, `failed`)
- worker identity
- worktree path
- commit SHA
- merge SHA
- timestamps and last error

### `tools/chapter_worker.py`
Claims the next pending chapter and drafts it in a worker worktree.

Worker behavior:
- claims one chapter atomically,
- resets the worktree clean before work,
- drafts the chapter,
- commits a chapter-sized commit,
- marks the queue job completed,
- or marks it failed with the error text.

### `tools/chapter_merge.py`
Cherry-picks completed worker commits onto `main` in canonical queue order and records merge completion back into the queue.

## Recommended operation

### 1. Initialize the queue

```bash
python tools/chapter_queue.py init --phase phase1
```

This scans source chapters and existing YAMLs.
- fully drafted chapters become `completed`
- missing chapters become `pending`

### 2. Launch workers in separate worktrees

Example:

```bash
python tools/chapter_worker.py \
  --coord-root /path/to/cartha-translation \
  --worker-id azure-a \
  --phase phase2 \
  --backend azure-openai \
  --model gpt-5.4 \
  --max-jobs 20
```

Run multiple workers at once with different worktrees / worker IDs.

### 3. Merge completed chapters

```bash
python tools/chapter_merge.py --coord-root /path/to/cartha-translation --push
```

This cherry-picks completed chapter commits onto `main` in canonical order.

### 4. Watch status

```bash
python tools/chapter_queue.py summary
python tools/chapter_queue.py ready
```

## Best practices

- One worker owns one chapter at a time.
- Use separate worktrees for concurrent workers.
- Keep `main` as the merge branch only.
- Let GPT-5.4 be the primary model path.
- Use OpenRouter GPT-5.4 only for narrow fallback cases when GPT-5.4 false-positives on scripture.
- Keep revisions out of the drafting queue until the first pass is complete.

## Practical recommendation

For the rest of the Bible:

1. finish the current Phase 1 first pass,
2. initialize a queue for the next phase,
3. run 8–16 chapter workers,
4. merge completed chapters continuously,
5. do revision and cross-reference after the first-pass draft of each phase is done.

In short:

> **Queue chapters, not verses. Merge chapters, not chaos.**
