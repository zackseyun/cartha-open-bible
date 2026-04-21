#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

from common import RAW_ROOT, ensure_dir, load_manifest, rel, resolve_text_ids, utc_now, write_json

USER_AGENT = 'Mozilla/5.0 (compatible; Phase-E-Nag-Hammadi-Scaffold/1.0)'
BLOCK_TAGS = {'script', 'style', 'noscript'}
BREAK_TAGS = {'p', 'br', 'div', 'li', 'ul', 'ol', 'section', 'article', 'header', 'footer', 'main', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}


class VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in BLOCK_TAGS:
            self._skip_depth += 1
        if tag in BREAK_TAGS:
            self._parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCK_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in BREAK_TAGS:
            self._parts.append('\n')

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = re.sub(r'\s+', ' ', data).strip()
        if cleaned:
            self._parts.append(cleaned)
            self._parts.append(' ')

    def text(self) -> str:
        joined = ''.join(self._parts)
        joined = re.sub(r' *\n+ *', '\n', joined)
        joined = re.sub(r'\n{3,}', '\n\n', joined)
        return joined.strip() + '\n'


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_html(url: str) -> str:
    return fetch_bytes(url).decode('utf-8', 'ignore')


def extract_title(html: str) -> str | None:
    match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    if not match:
        return None
    return re.sub(r'\s+', ' ', match.group(1)).strip()


def extract_license_excerpt(text: str) -> str | None:
    patterns = [
        r'(The following translation has been committed to the public domain[^\n]{0,400})',
        r'(we hereby dedicate all versings and alterations[^\n]{0,400})',
        r'(public domain[^\n]{0,400})',
        r'(exclusive permission[^\n]{0,400})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip()
    return None


def extract_othergospels_authors(html: str) -> list[str]:
    match = re.search(r"data-authors=['\"]([^'\"]+)['\"]", html)
    if not match:
        return []
    return [author.strip() for author in match.group(1).split(',') if author.strip()]


def render_othergospels_payload(payload: dict) -> str:
    lines: list[str] = []
    title = payload.get('full_name') or payload.get('name')
    if title:
        lines.append(str(title))
    prologue = payload.get('prologue')
    if prologue:
        lines.extend(['', str(prologue)])

    for chapter in payload.get('chapters', []):
        section = chapter.get('section')
        description = chapter.get('description')
        title = chapter.get('title')
        body = chapter.get('body') or []

        if section:
            lines.extend(['', str(section)])
        if title:
            lines.extend(['', str(title)])
        if description:
            lines.append(str(description))

        if isinstance(body, list):
            lines.extend(str(item) for item in body)
        elif isinstance(body, str):
            lines.append(body)

        footers = chapter.get('footers') or []
        if footers:
            lines.append('')
            lines.append('Footnotes:')
            for index, footer in enumerate(footers, start=1):
                lines.append(f'[{index}] {footer}')

    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


def fetch_dynamic_payload(url: str, witness: dict[str, str]) -> tuple[str | None, dict | None, str | None, list[str]]:
    html = fetch_html(url)
    authors = extract_othergospels_authors(html)
    if not authors:
        return html, None, None, []

    preferred = witness.get('preferred_author') or authors[0]
    if preferred not in authors:
        preferred = authors[0]

    payload_url = urljoin(url, f'{preferred}.json')
    try:
        payload = json.loads(fetch_bytes(payload_url).decode('utf-8', 'ignore'))
    except Exception:
        return html, None, None, authors
    rendered = render_othergospels_payload(payload)
    return html, payload, payload_url, authors


def fetch_witness(text_id: str, witness: dict[str, str], force: bool) -> dict[str, str | list[str] | None]:
    raw_dir = ensure_dir(RAW_ROOT / text_id)
    slug = witness['witness_id']
    html_path = raw_dir / f'{slug}.html'
    text_path = raw_dir / f'{slug}.txt'
    json_path = raw_dir / f'{slug}.json'

    if html_path.exists() and text_path.exists() and not force:
        visible_text = text_path.read_text(encoding='utf-8')
        cached = {
            'witness_id': slug,
            'status': 'cached',
            'url': witness['url'],
            'html_path': rel(html_path),
            'text_path': rel(text_path),
            'license_excerpt': extract_license_excerpt(visible_text),
        }
        if json_path.exists():
            cached['json_path'] = rel(json_path)
        return cached

    html, payload, payload_url, authors = fetch_dynamic_payload(witness['url'], witness)
    if html is None:
        html = fetch_html(witness['url'])

    if payload is not None:
        visible_text = render_othergospels_payload(payload)
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    else:
        parser = VisibleTextExtractor()
        parser.feed(html)
        visible_text = parser.text()

    html_path.write_text(html, encoding='utf-8')
    text_path.write_text(visible_text, encoding='utf-8')

    metadata = {
        'text_id': text_id,
        'witness_id': slug,
        'url': witness['url'],
        'fetched_at': utc_now(),
        'title': extract_title(html),
        'html_path': rel(html_path),
        'text_path': rel(text_path),
        'license_excerpt': extract_license_excerpt(visible_text),
        'available_authors': authors,
        'preferred_author': witness.get('preferred_author'),
        'payload_url': payload_url,
    }
    if payload is not None:
        metadata['json_path'] = rel(json_path)
    write_json(raw_dir / f'{slug}.meta.json', metadata)
    result = {'status': 'fetched', **metadata}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Fetch HTML witnesses from the Mattison/Zinner Nag Hammadi ecosystem.')
    parser.add_argument('--text', action='append', dest='texts', help='Text id to fetch. Repeatable.')
    parser.add_argument('--all', action='store_true', help='Fetch all configured texts.')
    parser.add_argument('--force', action='store_true', help='Re-fetch even if cached snapshots exist.')
    args = parser.parse_args()

    text_ids = resolve_text_ids(args.texts, args.all)
    results = []
    for text_id in text_ids:
        manifest = load_manifest(text_id)
        for witness in manifest.get('primary_witnesses', []):
            if witness.get('format') != 'html_page' or not witness.get('url'):
                continue
            results.append(fetch_witness(text_id, witness, args.force))

    report = {
        'generated_at': utc_now(),
        'count': len(results),
        'results': results,
    }
    write_json(RAW_ROOT / 'fetch-report.json', report)

    for result in results:
        suffix = f" ({result['payload_url']})" if result.get('payload_url') else ''
        print(f"[{result['status']}] {result['witness_id']} -> {result['text_path']}{suffix}")


if __name__ == '__main__':
    main()
