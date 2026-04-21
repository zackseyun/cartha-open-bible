#!/usr/bin/env python3
"""didache_secondary.py — secondary-source helpers for Didache revision.

Currently this module exposes the public-domain Schaff 1885 Didache
text as a chapter-mapped secondary witness using the Internet Archive
DjVu XML page text.
"""
from __future__ import annotations

import json
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SECONDARY_ROOT = REPO_ROOT / "sources" / "didache" / "secondary" / "schaff_1885"
CHAPTERS_DIR = SECONDARY_ROOT / "chapters"

SCHAFF_IA_ID = "oldestchurchman00schagoog"
SCHAFF_DJVU_XML_URL = f"https://archive.org/download/{SCHAFF_IA_ID}/{SCHAFF_IA_ID}_djvu.xml"

# Internet Archive DjVu page numbers containing the Schaff Didache text block.
CHAPTER_PAGE_MAP: dict[int, tuple[int, int]] = {
    1: (183, 187),
    2: (188, 190),
    3: (191, 194),
    4: (195, 199),
    5: (200, 201),
    6: (202, 204),
    7: (205, 207),
    8: (208, 210),
    9: (211, 214),
    10: (215, 218),
    11: (219, 224),
    12: (225, 225),
    13: (226, 228),
    14: (229, 231),
    15: (232, 233),
    16: (234, 238),
}


def fetch_page_texts() -> dict[int, str]:
    root = ET.fromstring(urllib.request.urlopen(SCHAFF_DJVU_XML_URL, timeout=60).read())
    out: dict[int, str] = {}
    for obj in root.iter("OBJECT"):
        page = obj.attrib.get("usemap") or ""
        if not page:
            params = {p.attrib.get("name"): p.attrib.get("value") for p in obj.findall("PARAM")}
            page = params.get("PAGE", "")
        m = re.search(r"_(\d+)\.djvu$", page)
        if not m:
            continue
        page_num = int(m.group(1))
        text = " ".join((w.text or "") for w in obj.iter("WORD"))
        if text.strip():
            out[page_num] = " ".join(text.split())
    return out


def build_secondary_chapter_files() -> dict:
    page_texts = fetch_page_texts()
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    payload: dict[str, dict[str, object]] = {}
    for chapter, (start, end) in CHAPTER_PAGE_MAP.items():
        pages = list(range(start, end + 1))
        joined = "\n\n".join(page_texts.get(p, "") for p in pages if page_texts.get(p, "").strip()).strip()
        out_path = CHAPTERS_DIR / f"ch{chapter:02d}.txt"
        out_path.write_text(joined + ("\n" if joined else ""), encoding="utf-8")
        payload[f"{chapter:02d}"] = {
            "chapter": chapter,
            "ia_pages": pages,
            "path": str(out_path.relative_to(REPO_ROOT)),
            "chars": len(joined),
        }

    map_path = SECONDARY_ROOT / "chapter_map.json"
    summary = {
        "source": "Schaff 1885 secondary Didache witness (IA DjVu XML text)",
        "internet_archive_id": SCHAFF_IA_ID,
        "chapters": payload,
    }
    map_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def load_chapter(chapter: int) -> str:
    path = CHAPTERS_DIR / f"ch{chapter:02d}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


if __name__ == "__main__":
    print(json.dumps(build_secondary_chapter_files(), ensure_ascii=False, indent=2))
