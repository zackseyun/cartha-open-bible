#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_ROOT = REPO_ROOT / 'sources' / 'nag_hammadi'
TEXTS_ROOT = SOURCES_ROOT / 'texts'
RAW_ROOT = SOURCES_ROOT / 'raw'
OCR_ROOT = SOURCES_ROOT / 'ocr'
OCR_JOBS_ROOT = OCR_ROOT / 'jobs'
OCR_OUTPUT_ROOT = OCR_ROOT / 'output'
STAGING_ROOT = SOURCES_ROOT / 'staging'
WITNESSES_ROOT = SOURCES_ROOT / 'witnesses'
PROMPTS_ROOT = SOURCES_ROOT / 'prompts'
CONSULT_REGISTRY_PATH = SOURCES_ROOT / 'consult_registry.json'
CATALOG_PATH = SOURCES_ROOT / 'catalog.json'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load_catalog() -> dict[str, Any]:
    return load_json(CATALOG_PATH)


def get_text_ids() -> list[str]:
    return list(load_catalog().get('texts', []))


def manifest_path(text_id: str) -> Path:
    return TEXTS_ROOT / text_id / 'manifest.json'


def load_manifest(text_id: str) -> dict[str, Any]:
    return load_json(manifest_path(text_id))


def iter_manifests(text_ids: list[str]) -> list[dict[str, Any]]:
    return [load_manifest(text_id) for text_id in text_ids]


def resolve_text_ids(selected: list[str] | None, all_texts: bool) -> list[str]:
    catalog_ids = get_text_ids()
    if all_texts or not selected:
        return catalog_ids
    invalid = [text_id for text_id in selected if text_id not in catalog_ids]
    if invalid:
        raise SystemExit(f"Unknown text id(s): {', '.join(invalid)}")
    return selected


def load_consult_registry() -> dict[str, dict[str, Any]]:
    entries = load_json(CONSULT_REGISTRY_PATH)
    return {entry['id']: entry for entry in entries}


def load_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rel_path = manifest.get('segment_index_path')
    if not rel_path:
        return []
    path = REPO_ROOT / rel_path
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def best_rel(path: Path) -> str:
    try:
        return rel(path.resolve())
    except Exception:
        return str(path.resolve())
