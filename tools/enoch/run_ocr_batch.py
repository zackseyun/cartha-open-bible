#!/usr/bin/env python3
"""run_ocr_batch.py — batch OCR many Enoch chapters in parallel.

Wraps `tools/enoch/run_ocr_31pro.py`'s per-chapter logic with a
ThreadPoolExecutor. Each chapter is independent, so chapters can run
concurrently; pages within a chapter still run sequentially (so the
per-chapter join file lands deterministically).

Resumable: skips chapters whose output JSON already exists unless
--force is passed. Per-chapter exceptions don't kill the batch.

Engine pinned to Gemini 3.1 Pro preview by default (the
2026-04-22 bake-off winner). Override with --model.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "enoch"))
import run_ocr_31pro  # type: ignore

OUT_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed"


def parse_chapters_arg(spec: str, available: set[int]) -> list[int]:
    if spec == "all":
        return sorted(available)
    chapters: set[int] = set()
    for part in spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            chapters.update(range(int(a), int(b) + 1))
        else:
            chapters.add(int(token))
    return sorted(c for c in chapters if c in available)


def chapter_already_done(edition: str, chapter: int) -> bool:
    edition_dir = OUT_ROOT / edition
    return (edition_dir / f"ch{chapter:02d}.json").exists() and (edition_dir / f"ch{chapter:02d}.txt").exists()


def run_one_chapter(edition: str, chapter: int, *, model: str, dpi: int) -> dict[str, Any]:
    started = time.time()
    try:
        summary = run_ocr_31pro.run_chapter(edition, chapter, force=True, model=model, dpi=dpi)
        return {
            "edition": edition,
            "chapter": chapter,
            "ok": True,
            "pages": summary.get("page_count", 0),
            "chars": summary.get("chars", 0),
            "duration_seconds": round(time.time() - started, 2),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - one chapter failure should not kill the batch
        return {
            "edition": edition,
            "chapter": chapter,
            "ok": False,
            "pages": 0,
            "chars": 0,
            "duration_seconds": round(time.time() - started, 2),
            "error": str(exc),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition", required=True, choices=["dillmann_1851", "charles_1906"])
    ap.add_argument("--chapters", default="all", help="'all', range '2-50', or list '1,5,10-12'")
    ap.add_argument("--workers", type=int, default=4, help="Concurrent chapter workers")
    ap.add_argument("--force", action="store_true", help="Re-OCR chapters even if cached chN.json exists")
    ap.add_argument("--model", default=run_ocr_31pro.DEFAULT_MODEL)
    ap.add_argument("--dpi", type=int, default=400)
    args = ap.parse_args()

    page_map = run_ocr_31pro.load_map()
    edition_chapters = page_map["editions"][args.edition]["chapters"]
    available = {int(k) for k in edition_chapters.keys()}
    chapters = parse_chapters_arg(args.chapters, available)
    if not chapters:
        print(f"No chapters resolved from spec={args.chapters!r}; available={sorted(available)[:10]}…")
        return 1

    pending: list[int] = []
    skipped: list[int] = []
    for c in chapters:
        if not args.force and chapter_already_done(args.edition, c):
            skipped.append(c)
            continue
        pending.append(c)

    print(f"[batch] {args.edition}: {len(pending)} pending, {len(skipped)} cached, {args.workers} workers, model={args.model}")
    if not pending:
        return 0

    started = time.time()
    completed = 0
    failed: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        future_map = {
            ex.submit(run_one_chapter, args.edition, c, model=args.model, dpi=args.dpi): c
            for c in pending
        }
        for fut in as_completed(future_map):
            c = future_map[fut]
            res = fut.result()
            summaries.append(res)
            completed += 1
            tag = "OK " if res["ok"] else "FAIL"
            print(
                f"  [{completed}/{len(pending)}] ch {c:>3}: {tag} pages={res['pages']} chars={res['chars']} "
                f"dur={res['duration_seconds']}s"
                + (f" err={res['error'][:80]!r}" if res["error"] else ""),
                flush=True,
            )
            if not res["ok"]:
                failed.append(res)

    duration = round(time.time() - started, 2)
    print()
    print(f"[batch] {args.edition}: completed in {duration}s — ok={len(pending) - len(failed)} fail={len(failed)}")
    if failed:
        print("  failures:")
        for f in failed:
            print(f"    ch {f['chapter']}: {f['error'][:160]}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
