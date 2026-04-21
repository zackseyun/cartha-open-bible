#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from common import RAW_ROOT, load_manifest

TRUTH_HEADINGS = [
    'Prologue',
    'Error and Forgetfulness',
    'The Gospel',
    'The Book of the Living',
    'The Return to Unity',
    'The Parable of the Jars',
    'Coming into Being',
    'The Parable of the Nightmares',
    'The Revelation of the Son',
    'The Parable of the Sheep',
    'Doing the Father’s Will',
    'Restoring what was Needed',
    'The Father’s Paradise',
    'The Father’s Name',
    'The Place of Rest',
    'Conclusion',
]

THOMAS_SAYING_RE = re.compile(r'^Saying\s+(\d+):\s*(.+?)\s*$')
THUNDER_VERSE_RE = re.compile(r'^\*\*(\d+)\.\*\*\s*')


def primary_witness_text_path(text_id: str) -> Path:
    manifest = load_manifest(text_id)
    for witness in manifest.get('primary_witnesses', []):
        if witness.get('role') == 'primary_coptic' and witness.get('format') == 'html_page':
            return RAW_ROOT / text_id / f"{witness['witness_id']}.txt"
    for witness in manifest.get('primary_witnesses', []):
        if witness.get('format') == 'html_page':
            return RAW_ROOT / text_id / f"{witness['witness_id']}.txt"
    raise FileNotFoundError(f'No html/text witness configured for {text_id}')


def primary_witness_json_path(text_id: str) -> Path:
    manifest = load_manifest(text_id)
    for witness in manifest.get('primary_witnesses', []):
        if witness.get('role') == 'primary_coptic' and witness.get('format') == 'html_page':
            path = RAW_ROOT / text_id / f"{witness['witness_id']}.json"
            if path.exists():
                return path
    raise FileNotFoundError(f'No primary json witness found for {text_id}')


def extract_thomas_segments(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    segments: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    body_lines: list[str] = []

    for line_no, line in enumerate(lines, start=1):
        match = THOMAS_SAYING_RE.match(line)
        if match:
            if current is not None:
                current['end_ref'] = str(line_no - 1)
                current['excerpt'] = '\n'.join([current['heading'], *body_lines]).strip()
                segments.append(current)
            saying_number = int(match.group(1))
            title = match.group(2).strip()
            current = {
                'segment_id': f'{saying_number:03d}',
                'label': f'Saying {saying_number} — {title}',
                'heading': f'Saying {saying_number}: {title}',
                'status': 'planned',
                'start_ref': str(line_no),
                'end_ref': str(line_no),
                'chapter_index': '',
                'block_index': '',
                'notes': '',
            }
            body_lines = []
        elif current is not None:
            body_lines.append(line)

    if current is not None:
        current['end_ref'] = str(len(lines))
        current['excerpt'] = '\n'.join([current['heading'], *body_lines]).strip()
        segments.append(current)

    return segments


def extract_truth_segments(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    heading_positions: list[tuple[str, int]] = []
    for heading in TRUTH_HEADINGS:
        try:
            index = lines.index(heading)
        except ValueError as exc:
            raise ValueError(f'Could not find Truth heading: {heading}') from exc
        heading_positions.append((heading, index + 1))

    segments: list[dict[str, str]] = []
    for idx, (heading, start_line) in enumerate(heading_positions, start=1):
        if idx < len(heading_positions):
            end_line = heading_positions[idx][1] - 1
        else:
            end_line = lines.index('Notes on Translation')
        excerpt = '\n'.join(lines[start_line - 1:end_line]).strip()
        segments.append({
            'segment_id': f'{idx:03d}',
            'label': heading,
            'heading': heading,
            'status': 'planned',
            'start_ref': str(start_line),
            'end_ref': str(end_line),
            'chapter_index': '',
            'block_index': '',
            'notes': '',
            'excerpt': excerpt,
        })
    return segments


def extract_thunder_segments(payload: dict) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    counter = 1
    for chapter_index, chapter in enumerate(payload.get('chapters', []), start=1):
        chapter_title = chapter.get('title') or f'Chapter {chapter_index}'
        for block_index, body in enumerate(chapter.get('body', []), start=1):
            match = THUNDER_VERSE_RE.match(body)
            verse_label = match.group(1) if match else str(block_index)
            segments.append({
                'segment_id': f'{counter:03d}',
                'label': f'{chapter_title} — {verse_label}',
                'heading': chapter_title,
                'status': 'planned',
                'start_ref': f'{chapter_index}.{block_index}',
                'end_ref': f'{chapter_index}.{block_index}',
                'chapter_index': str(chapter_index),
                'block_index': str(block_index),
                'notes': '',
                'excerpt': body.strip(),
            })
            counter += 1
    return segments


def load_extracted_segments(text_id: str) -> list[dict[str, str]]:
    if text_id == 'gospel_of_thomas':
        return extract_thomas_segments(primary_witness_text_path(text_id).read_text(encoding='utf-8'))
    if text_id == 'gospel_of_truth':
        return extract_truth_segments(primary_witness_text_path(text_id).read_text(encoding='utf-8'))
    if text_id == 'thunder_perfect_mind':
        payload = json.loads(primary_witness_json_path(text_id).read_text(encoding='utf-8'))
        return extract_thunder_segments(payload)
    raise ValueError(f'Unsupported text id for segment extraction: {text_id}')
