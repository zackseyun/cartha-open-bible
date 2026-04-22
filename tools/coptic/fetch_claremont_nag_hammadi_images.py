#!/usr/bin/env python3
"""Fetch Nag Hammadi facsimile page images from the Claremont CCDL.

Two preconfigured text fetch targets are supported:
- gospel_of_truth: curated Codex I page list from Gospels.net manuscript info
- thunder_perfect_mind: Codex VI pages 13-21 (tractate span)

Outputs a staging directory containing:
- one JPEG per codex page
- manifest.json with record metadata and image URIs
- sources.txt compatible with `tools/coptic/ocr_coptic.py register`
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from common import REPO_ROOT, STAGING_ROOT, ensure_dir, rel, utc_now, write_json

USER_AGENT = 'Mozilla/5.0 (compatible; Phase-E-Claremont-Fetch/1.0)'
GOSPELS_MANUSCRIPT_URL = 'https://www.gospels.net/manuscript'
CCDL_API_BASE = 'https://ccdl.claremont.edu/digital/api'
CCDL_DIGITAL_BASE = 'https://ccdl.claremont.edu/digital'

TRUTH_PAGE_SPEC = [16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 43]
THUNDER_PAGE_SPEC = list(range(13, 22))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode('utf-8', 'replace')


def fetch_json(url: str) -> dict[str, Any]:
    return json.loads(fetch_text(url))


def download_binary(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def absolutize(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return urllib.parse.urljoin(CCDL_DIGITAL_BASE + '/', url.lstrip('/'))


def write_image_file(target_dir: Path, filename: str, rec: dict[str, Any]) -> None:
    image_uri = absolutize(rec.get('image_uri'))
    download_uri = absolutize(rec.get('download_uri'))
    target_path = target_dir / filename
    try:
        if not image_uri:
            raise urllib.error.HTTPError(download_uri or '', 404, 'missing image_uri', None, None)
        target_path.write_bytes(download_binary(image_uri))
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 403 or not download_uri:
            raise
    with tempfile.TemporaryDirectory(prefix='ccdl_jp2_') as tmpdir:
        tmpdir_path = Path(tmpdir)
        jp2_path = tmpdir_path / 'page.jp2'
        subprocess.run(['curl', '-L', '-A', USER_AGENT, '--max-time', '240', '-o', str(jp2_path), download_uri], check=True, capture_output=True)
        raw_jp2 = jp2_path.read_bytes()
        jpg_path = tmpdir_path / 'page.jpg'
        subprocess.run(['sips', '-s', 'format', 'jpeg', str(jp2_path), '--out', str(jpg_path)], check=True, capture_output=True)
        target_path.write_bytes(jpg_path.read_bytes())


def truth_page_list() -> list[int]:
    html = fetch_text(GOSPELS_MANUSCRIPT_URL)
    if 'The Gospel of Truth' not in html:
        raise RuntimeError('Could not confirm the Gospel of Truth entry on gospels.net/manuscript')
    return TRUTH_PAGE_SPEC


def choose_truth_record_url(page: int) -> str:
    title = f'Codex I, papyrus page {page}'
    url = f'{CCDL_API_BASE}/search/searchterm/{urllib.parse.quote(title, safe="")}/field/title/mode/all/conn/and'
    data = fetch_json(url)
    items = [item for item in (data.get('items') or []) if item.get('title') == title]
    if not items:
        raise RuntimeError(f'No CCDL item found for {title}')
    enriched: list[tuple[tuple[int, str], str]] = []
    for item in items:
        rec = resolve_record(f'{CCDL_DIGITAL_BASE}/collection/nha/id/{item["itemId"]}/rec/1')
        series = str(rec.get('series', ''))
        # Empirically, the N-series scan gives a cleaner Gospel of Truth p16 OCR start than M-series.
        series_rank = {'N-Series': 0, 'Jung': 1, 'M-Series': 2, 'A-Series': 3}.get(series, 4)
        enriched.append(((series_rank, str(item['itemId'])), rec['record_url']))
    return sorted(enriched, key=lambda pair: pair[0])[0][1]


def search_record_url_by_title(title: str) -> str:
    url = f'{CCDL_API_BASE}/search/searchterm/{urllib.parse.quote(title, safe="")}/field/title/mode/all/conn/and'
    data = fetch_json(url)
    items = data.get('items') or []
    exact = [item for item in items if item.get('title') == title]
    if not exact:
        raise RuntimeError(f'No exact CCDL item found for title: {title}')
    item = exact[0]
    item_id = item['itemId']
    return f'{CCDL_DIGITAL_BASE}/collection/nha/id/{item_id}/rec/1'


def resolve_record(record_url: str) -> dict[str, Any]:
    match = re.search(r'/collection/nha/id/(\d+)', record_url)
    if not match:
        raise RuntimeError(f'Could not parse item id from {record_url}')
    item_id = match.group(1)
    item = fetch_json(f'{CCDL_API_BASE}/singleitem/collection/nha/id/{item_id}')
    fields = {field['key']: field.get('value') for field in item.get('fields', []) if isinstance(field, dict) and field.get('key')}
    return {
        'item_id': item_id,
        'title': fields.get('title', ''),
        'description': fields.get('descri', ''),
        'series': fields.get('series', ''),
        'codex': fields.get('codex', ''),
        'record_url': record_url,
        'image_uri': item.get('imageUri'),
        'iiif_info_uri': item.get('iiifInfoUri'),
        'download_uri': item.get('downloadUri'),
    }


def write_sources_file(target_dir: Path, records: list[dict[str, Any]]) -> None:
    lines = []
    for rec in records:
        lines.append(f"{rec['filename']} <- {rec['image_uri']}")
    (target_dir / 'sources.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def fetch_truth(target_dir: Path) -> Path:
    records: list[dict[str, Any]] = []
    for page in truth_page_list():
        rec = resolve_record(choose_truth_record_url(page))
        filename = f'nhc_i3_page_{page:02d}.jpg'
        write_image_file(target_dir, filename, rec)
        rec['filename'] = filename
        rec['codex_page'] = page
        records.append(rec)
    write_json(target_dir / 'manifest.json', {
        'fetched_at': utc_now(),
        'text_id': 'gospel_of_truth',
        'witness_id': 'nhc_i_3_facsimile_primary',
        'source': 'Claremont CCDL via curated Gospels.net manuscript links',
        'records': records,
    })
    write_sources_file(target_dir, records)
    return target_dir


def fetch_thunder(target_dir: Path) -> Path:
    records: list[dict[str, Any]] = []
    for page in THUNDER_PAGE_SPEC:
        rec = resolve_record(search_record_url_by_title(f'Codex VI, papyrus page {page}'))
        filename = f'nhc_vi2_page_{page:02d}.jpg'
        write_image_file(target_dir, filename, rec)
        rec['filename'] = filename
        rec['codex_page'] = page
        records.append(rec)
    write_json(target_dir / 'manifest.json', {
        'fetched_at': utc_now(),
        'text_id': 'thunder_perfect_mind',
        'witness_id': 'nhc_vi_2_facsimile_primary',
        'source': 'Claremont CCDL title search (Codex VI pages 13-21)',
        'records': records,
    })
    write_sources_file(target_dir, records)
    return target_dir


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--text', choices=['gospel_of_truth', 'thunder_perfect_mind'], required=True)
    ap.add_argument('--out-dir', help='Optional staging target dir override')
    args = ap.parse_args()

    if args.out_dir:
        target_dir = Path(args.out_dir).expanduser().resolve()
    elif args.text == 'gospel_of_truth':
        target_dir = ensure_dir(STAGING_ROOT / 'gospel_of_truth' / 'nhc_i_3_facsimile_primary')
    else:
        target_dir = ensure_dir(STAGING_ROOT / 'thunder_perfect_mind' / 'nhc_vi_2_facsimile_primary')
    ensure_dir(target_dir)

    if args.text == 'gospel_of_truth':
        path = fetch_truth(target_dir)
    else:
        path = fetch_thunder(target_dir)
    print(rel(path))


if __name__ == '__main__':
    main()
