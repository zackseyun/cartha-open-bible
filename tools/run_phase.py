#!/usr/bin/env python3
"""
run_phase.py — Generate and commit a phase of Cartha Open Bible drafts.

Phase 0 uses a single substantive pilot commit after local drafting.
Phase 1 and beyond can use chapter-sized commits for steadier progress.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
from collections import Counter
from typing import Any

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import consistency_lint  # noqa: E402
import draft  # noqa: E402
import sblgnt  # noqa: E402
import wlc  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

PHASES: dict[str, dict[str, Any]] = {
    "phase0": {
        "label": "Phase 0 — Philippians",
        "books": ["PHP"],
        "testament": "nt",
        "tag": "v0.1-preview-philippians",
        "lint_phase_name": "phase0-philippians",
        "lint_report": REPO_ROOT / "lint_reports" / "phase0-philippians.md",
        "commit_mode": "verse",
    },
    "phase1": {
        "label": "Phase 1 — Pauline epistles",
        "books": ["ROM", "1CO", "2CO", "GAL", "EPH", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM"],
        "testament": "nt",
        "tag": "v0.2-pauline",
        "lint_phase_name": "phase1-pauline",
        "lint_report": REPO_ROOT / "lint_reports" / "phase1-pauline.md",
        "commit_mode": "chapter",
    },
    "phase2": {
        "label": "Phase 2 — Gospels + Acts",
        "books": ["MAT", "MRK", "LUK", "JHN", "ACT"],
        "testament": "nt",
        "tag": "v0.3-gospels",
        "lint_phase_name": "phase2-gospels",
        "lint_report": REPO_ROOT / "lint_reports" / "phase2-gospels.md",
        "commit_mode": "chapter",
    },
    "phase3": {
        "label": "Phase 3 — General epistles + Revelation",
        "books": ["HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"],
        "testament": "nt",
        "tag": "v0.4-nt-complete",
        "lint_phase_name": "phase3-nt-complete",
        "lint_report": REPO_ROOT / "lint_reports" / "phase3-nt-complete.md",
        "commit_mode": "chapter",
    },
    "phase4": {
        "label": "Phase 4 — Torah",
        "books": ["GEN", "EXO", "LEV", "NUM", "DEU"],
        "testament": "ot",
        "tag": "v0.5-torah",
        "lint_phase_name": "phase4-torah",
        "lint_report": REPO_ROOT / "lint_reports" / "phase4-torah.md",
        "commit_mode": "chapter",
    },
    "phase5": {
        "label": "Phase 5 — Former Prophets",
        "books": ["JOS", "JDG", "1SA", "2SA", "1KI", "2KI"],
        "testament": "ot",
        "tag": "v0.6-former-prophets",
        "lint_phase_name": "phase5-former-prophets",
        "lint_report": REPO_ROOT / "lint_reports" / "phase5-former-prophets.md",
        "commit_mode": "chapter",
    },
    "phase6": {
        "label": "Phase 6 — Writings",
        "books": ["PSA", "PRO", "JOB", "RUT", "SNG", "ECC", "LAM", "EST", "DAN", "EZR", "NEH", "1CH", "2CH"],
        "testament": "ot",
        "tag": "v0.7-writings",
        "lint_phase_name": "phase6-writings",
        "lint_report": REPO_ROOT / "lint_reports" / "phase6-writings.md",
        "commit_mode": "chapter",
    },
    "phase7": {
        "label": "Phase 7 — Latter Prophets",
        "books": ["ISA", "JER", "EZK", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"],
        "testament": "ot",
        "tag": "v0.8-latter-prophets",
        "lint_phase_name": "phase7-latter-prophets",
        "lint_report": REPO_ROOT / "lint_reports" / "phase7-latter-prophets.md",
        "commit_mode": "chapter",
    },
}


def git(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def ensure_clean_worktree() -> None:
    status = git("status", "--porcelain", capture_output=True).stdout.strip()
    if status:
        raise RuntimeError(
            "Git worktree is not clean. Commit or stash existing changes before running a phase."
        )


def lexical_summary(record: dict[str, Any], limit: int = 3) -> str:
    entries = []
    for decision in (record.get("lexical_decisions") or [])[:limit]:
        source = str(decision.get("source_word", "") or "").strip()
        chosen = str(decision.get("chosen", "") or "").strip()
        if source and chosen:
            entries.append(f"{source}→{chosen}")

    if not entries:
        return "Lexical decisions recorded in YAML."

    summary = "; ".join(entries)
    if len(record.get("lexical_decisions") or []) > limit:
        summary += "; +more"
    return summary[:220]


def verse_commit_message(record: dict[str, Any]) -> str:
    book_code, chapter, verse = str(record["id"]).split(".")
    return (
        f"draft: {book_code} {int(chapter)}:{int(verse)} via GPT 5.4\n\n"
        f"{lexical_summary(record)}\n\n"
        "Generated-By: codex-gpt-5.4\n"
    )


def chapter_commit_message(
    book_code: str,
    chapter: int,
    records: list[dict[str, Any]],
) -> str:
    if not records:
        raise ValueError("chapter_commit_message requires at least one record")

    verses = [
        int(str(record["id"]).split(".")[2])
        for record in records
    ]
    verses.sort()
    verse_span = f"{verses[0]}:{verses[0]}"  # temporary placeholder
    if verses[0] == verses[-1]:
        reference_part = f"{chapter}:{verses[0]}"
    else:
        reference_part = f"{chapter}:{verses[0]}-{verses[-1]}"

    lexical_bits: list[str] = []
    seen: set[str] = set()
    for record in records:
        for decision in (record.get("lexical_decisions") or [])[:3]:
            source = str(decision.get("source_word", "") or "").strip()
            chosen = str(decision.get("chosen", "") or "").strip()
            pair = f"{source}→{chosen}"
            if source and chosen and pair not in seen:
                lexical_bits.append(pair)
                seen.add(pair)
            if len(lexical_bits) >= 6:
                break
        if len(lexical_bits) >= 6:
            break

    summary = "; ".join(lexical_bits[:6]) if lexical_bits else "Chapter draft batch with lexical decisions recorded in YAML."
    if len(summary) > 260:
        summary = summary[:257] + "..."

    return (
        f"draft: {book_code} {reference_part} via GPT 5.4\n\n"
        f"{summary}\n\n"
        "Generated-By: codex-gpt-5.4\n"
    )


def commit_paths(paths: list[pathlib.Path], message: str) -> None:
    git("add", *[str(path.relative_to(REPO_ROOT)) for path in paths])
    subprocess.run(
        ["git", "commit", "-F", "-"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        input=message,
    )


def write_failed_verses(verse_ids: list[str]) -> pathlib.Path | None:
    if not verse_ids:
        if draft.FAILED_VERSES_PATH.exists():
            draft.FAILED_VERSES_PATH.unlink()
        return None

    draft.FAILED_VERSES_PATH.write_text(
        "\n".join(verse_ids) + "\n",
        encoding="utf-8",
    )
    return draft.FAILED_VERSES_PATH


def collect_phase_records(phase: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for book_code in phase["books"]:
        slug = draft.book_slug_for_code(book_code)
        book_root = REPO_ROOT / "translation" / phase["testament"] / slug
        for path in sorted(book_root.glob("*/*.yaml")):
            records.append(yaml.safe_load(path.read_text(encoding="utf-8")))
    return records


def resolve_active_books(phase: dict[str, Any], selected_books: list[str] | None) -> list[str]:
    if not selected_books:
        return list(phase["books"])
    unknown = [book for book in selected_books if book not in phase["books"]]
    if unknown:
        raise RuntimeError(
            f"Selected books {unknown} are not in {phase['label']}. Allowed: {phase['books']}"
        )
    return list(selected_books)


def build_phase_stats(phase: dict[str, Any]) -> dict[str, Any]:
    records = collect_phase_records(phase)
    contested_verses: list[str] = []
    philosophy_counter: Counter[str] = Counter()
    model_versions: Counter[str] = Counter()
    lemma_counter: Counter[str] = Counter()
    contested_terms = draft.load_contested_terms()
    contested_norms = set(contested_terms)

    for record in records:
        philosophy_counter[str(record["translation"]["philosophy"])] += 1
        model_versions[str(record["ai_draft"]["model_version"])] += 1

        verse_has_contested = bool(record.get("theological_decisions"))
        source_verse = consistency_lint.load_source_verse(record)
        if source_verse is not None:
            for word in source_verse.words:
                if draft.normalize_term(word.lemma) in contested_norms:
                    verse_has_contested = True
                    break

        if verse_has_contested:
            contested_verses.append(str(record["id"]))

    for book_code in phase["books"]:
        for verse in draft.iter_source_verses(book_code):
            for word in verse.words:
                word_text = getattr(word, "word", getattr(word, "text", ""))
                if any(ch.isalpha() for ch in word_text):
                    lemma_counter[word.lemma] += 1

    return {
        "records": records,
        "contested_verses": contested_verses,
        "philosophy_counter": philosophy_counter,
        "model_versions": model_versions,
        "top_lemmas": lemma_counter.most_common(10),
    }


def update_changelog(phase: dict[str, Any], stats: dict[str, Any], lint_report: pathlib.Path) -> None:
    tag = phase["tag"]
    verse_count = len(stats["records"])
    model_versions = ", ".join(
        f"`{version}` × {count}"
        for version, count in stats["model_versions"].most_common()
    )
    contested = (
        ", ".join(stats["contested_verses"][:12]) + ("…" if len(stats["contested_verses"]) > 12 else "")
        if stats["contested_verses"] else "None noted in the pilot draft set."
    )

    release_plan = """## Release plan

- `v0.1-preview-philippians` — Philippians (pilot)
- `v0.2-pauline` — Romans, 1–2 Corinthians, Galatians, Ephesians, Colossians, 1–2 Thessalonians, 1–2 Timothy, Titus, Philemon
- `v0.3-gospels` — Matthew, Mark, Luke, John, Acts
- `v0.4-nt-complete` — General epistles + Revelation
- `v0.5-torah` — Genesis through Deuteronomy
- `v0.6-former-prophets` — Joshua through 2 Kings
- `v0.7-writings` — Psalms, Proverbs, Job, Ruth, Song of Songs, Ecclesiastes, Lamentations, Esther, Daniel, Ezra-Nehemiah, Chronicles
- `v0.8-latter-prophets` — Isaiah, Jeremiah, Ezekiel, the Twelve
- `v1.0-complete` — Full Bible, all phases re-reviewed and re-linted
"""

    release_entry = f"""## {tag} — {draft.utc_timestamp()[:10]}

- Phase: {phase["label"]}
- Verse count: {verse_count}
- Drafter model versions: {model_versions}
- Consistency lint: `{lint_report.relative_to(REPO_ROOT)}`
- Deferred contested decisions: {contested}
"""

    unreleased_block = """## Unreleased

- Repository scaffold
- DOCTRINE.md, METHODOLOGY.md first drafts
- Per-verse YAML schema defined (`schema/verse.schema.json`)
"""

    new_changelog = (
        "# Changelog\n\n"
        "All phase releases are documented here. Individual verse revisions are\n"
        "tracked in git history on the per-verse YAML files.\n\n"
        f"{unreleased_block}\n"
        f"{release_entry}\n"
        f"{release_plan}\n"
    )

    CHANGELOG_PATH.write_text(new_changelog, encoding="utf-8")


def finalize_phase(
    phase_name: str,
    *,
    selected_books: list[str] | None = None,
    no_commit: bool = False,
) -> dict[str, Any]:
    phase = PHASES[phase_name]
    active_books = resolve_active_books(phase, selected_books)
    flags, lint_report, _scanned = consistency_lint.run_lint(
        phase=phase["lint_phase_name"],
        testament=phase["testament"],
        book_filters={draft.book_slug_for_code(book_code) for book_code in active_books},
        output_path=phase["lint_report"],
    )
    if flags:
        raise RuntimeError(
            f"Consistency lint found {len(flags)} unresolved flag(s). See {lint_report.relative_to(REPO_ROOT)}"
        )

    scoped_phase = dict(phase)
    scoped_phase["books"] = active_books
    stats = build_phase_stats(scoped_phase)
    update_changelog(phase, stats, lint_report)

    if not no_commit:
        commit_paths(
            [lint_report, CHANGELOG_PATH],
            (
                f"release: {phase['tag']} summary\n\n"
                f"Phase summary for {phase['label']}.\n\n"
                "Generated-By: codex-gpt-5.4\n"
            ),
        )
        tag_exists = git("tag", "-l", phase["tag"], capture_output=True).stdout.strip()
        if not tag_exists:
            subprocess.run(["git", "tag", phase["tag"]], cwd=REPO_ROOT, check=True)

    return {
        "lint_report": lint_report,
        **stats,
    }


def run_phase(
    phase_name: str,
    *,
    backend: str,
    model: str,
    temperature: float,
    prompt_id: str,
    selected_books: list[str] | None,
    limit: int | None,
    max_chapters: int | None,
    no_commit: bool,
) -> dict[str, Any]:
    phase = PHASES[phase_name]
    active_books = resolve_active_books(phase, selected_books)
    failed_verses: list[str] = []
    drafted_count = 0
    created_paths: list[pathlib.Path] = []
    chapter_commits = 0
    current_chapter_key: tuple[str, int] | None = None
    chapter_paths: list[pathlib.Path] = []
    chapter_records: list[dict[str, Any]] = []

    def flush_chapter_batch() -> None:
        nonlocal chapter_commits, chapter_paths, chapter_records, current_chapter_key
        if phase["commit_mode"] != "chapter":
            chapter_paths = []
            chapter_records = []
            current_chapter_key = None
            return
        if chapter_paths and not no_commit and current_chapter_key is not None:
            book_code, chapter = current_chapter_key
            commit_paths(
                chapter_paths,
                chapter_commit_message(book_code, chapter, chapter_records),
            )
            chapter_commits += 1
        chapter_paths = []
        chapter_records = []
        current_chapter_key = None

    for book_code in active_books:
        for verse in draft.iter_source_verses(book_code):
            chapter_key = (book_code, verse.chapter)
            if current_chapter_key is None:
                current_chapter_key = chapter_key
            elif chapter_key != current_chapter_key:
                flush_chapter_batch()
                current_chapter_key = chapter_key
                if max_chapters is not None and chapter_commits >= max_chapters:
                    break

            if limit is not None and drafted_count >= limit:
                break

            output_path = draft.translation_path_for_verse(verse)
            if output_path.exists():
                continue

            try:
                result = draft.retry_draft_verse(
                    verse,
                    backend=backend,
                    model=model,
                    temperature=temperature,
                    prompt_id=prompt_id,
                )
            except Exception as exc:
                print(f"FAILED {verse.canonical_id}: {exc}", file=sys.stderr)
                failed_verses.append(verse.canonical_id)
                continue

            drafted_count += 1
            created_paths.append(result.output_path)
            print(f"Wrote {result.output_path.relative_to(REPO_ROOT)}")

            if phase["commit_mode"] == "verse" and not no_commit:
                commit_paths([result.output_path], verse_commit_message(result.record))
            elif phase["commit_mode"] == "chapter":
                chapter_paths.append(result.output_path)
                chapter_records.append(result.record)

        flush_chapter_batch()
        if max_chapters is not None and chapter_commits >= max_chapters:
            break
        if limit is not None and drafted_count >= limit:
            break

    failed_path = write_failed_verses(failed_verses)
    if failed_path and not no_commit:
        commit_paths(
            [failed_path],
            "chore: record failed verse retries\n\nGenerated-By: codex-gpt-5.4\n",
        )

    if failed_verses:
        raise RuntimeError(
            f"{len(failed_verses)} verse(s) failed. See {draft.FAILED_VERSES_PATH.relative_to(REPO_ROOT)}"
        )

    if limit is not None:
        return {
            "drafted_count": drafted_count,
            "created_paths": created_paths,
        }
    if max_chapters is not None:
        return {
            "drafted_count": drafted_count,
            "created_paths": created_paths,
            "chapter_commits": chapter_commits,
        }

    return finalize_phase(phase_name, selected_books=active_books, no_commit=no_commit)


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=sorted(PHASES), default="phase0")
    parser.add_argument(
        "--backend",
        default=draft.DEFAULT_BACKEND,
        choices=[draft.BACKEND_CODEX, draft.BACKEND_OPENAI],
    )
    parser.add_argument("--model", default=draft.DEFAULT_MODEL_ID)
    parser.add_argument("--temperature", type=float, default=draft.DEFAULT_TEMPERATURE)
    parser.add_argument("--prompt-id", default=draft.DEFAULT_PROMPT_ID)
    parser.add_argument("--books", nargs="*", help="Optional subset of phase book codes to process")
    parser.add_argument("--limit", type=int, help="Only draft the first N missing verses, then stop")
    parser.add_argument("--max-chapters", type=int, help="Stop after drafting/committing N chapter batches")
    parser.add_argument("--no-commit", action="store_true", help="Write files but skip git commits and tagging")
    args = parser.parse_args()

    if args.backend == draft.BACKEND_OPENAI and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set for openai-sdk backend.", file=sys.stderr)
        return 2
    if args.backend == draft.BACKEND_CODEX and not draft.codex_login_available():
        print("ERROR: codex-cli backend requested but Codex is not logged in.", file=sys.stderr)
        return 2

    try:
        if not args.no_commit:
            ensure_clean_worktree()
        result = run_phase(
            args.phase,
            backend=args.backend,
            model=args.model,
            temperature=args.temperature,
            prompt_id=args.prompt_id,
            selected_books=args.books,
            limit=args.limit,
            max_chapters=args.max_chapters,
            no_commit=args.no_commit,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.limit is not None:
        print(f"Drafted {result['drafted_count']} verse(s) in limited mode.")
        return 0
    if args.max_chapters is not None:
        print(
            f"Drafted {result['drafted_count']} verse(s) across "
            f"{result['chapter_commits']} chapter batch(es)."
        )
        return 0

    print(f"Completed {PHASES[args.phase]['label']}")
    print(f"Contested verses: {', '.join(result['contested_verses']) or 'None'}")
    print(
        "Philosophy distribution: "
        + ", ".join(f"{name}={count}" for name, count in result["philosophy_counter"].most_common())
    )
    print(
        "Top lemmas: "
        + ", ".join(f"{lemma}×{count}" for lemma, count in result["top_lemmas"])
    )
    print(f"Lint report: {result['lint_report'].relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
