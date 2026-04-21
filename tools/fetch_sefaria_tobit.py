#!/usr/bin/env python3
"""fetch_sefaria_tobit.py — pull Hebrew Tobit (Neubauer 1878) from Sefaria.

Sefaria hosts A. Neubauer's 1878 Hebrew back-translation of Tobit
(Public Domain). This is not an ancient Hebrew witness — the Qumran
Aramaic fragments (4Q196-200) are the actual ancient evidence — but
it's the best publicly-available full Hebrew text and is useful as
a translation-phase reference for proper names and idioms.

Output: sources/lxx/hebrew_parallels/sefaria_tobit.json

License note: Neubauer's edition is PD (1878, author died 1907); the
Sefaria digital text is also marked Public Domain. Free to redistribute.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "sources" / "lxx" / "hebrew_parallels" / "sefaria_tobit.json"

CHAPTERS = 13  # per Sefaria index: schema.lengths[0]


def fetch_chapter(n: int) -> dict:
    url = f"https://www.sefaria.org/api/v3/texts/{urllib.parse.quote(f'Tobit.{n}')}?version=hebrew&version=english"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def strip_html(s: str) -> str:
    import re
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def main() -> int:
    chapters: dict[str, dict] = {}
    he_ver_title = he_ver_license = he_ver_source = None
    for n in range(1, CHAPTERS + 1):
        print(f"fetching Tobit {n} ...", flush=True)
        try:
            data = fetch_chapter(n)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            time.sleep(2)
            continue
        versions = data.get("versions", [])
        he_ver = next((v for v in versions if v.get("language") == "he"), None)
        en_ver = next((v for v in versions if v.get("language") == "en"), None)
        he_text = he_ver.get("text", []) if he_ver else []
        en_text = en_ver.get("text", []) if en_ver else []
        if he_ver and not he_ver_title:
            he_ver_title = he_ver.get("versionTitle")
            he_ver_license = he_ver.get("license")
            he_ver_source = he_ver.get("versionSource")
        verses = []
        max_len = max(len(he_text), len(en_text))
        for i in range(max_len):
            hv = strip_html(he_text[i] if i < len(he_text) else "")
            ev = strip_html(en_text[i] if i < len(en_text) else "")
            verses.append({"verse": i + 1, "hebrew": hv, "english": ev})
        heb_count = sum(1 for v in verses if v["hebrew"])
        chapters[str(n)] = {
            "chapter": n,
            "verses": verses,
            "hebrew_count": heb_count,
            "heVersionTitle": he_ver_title,
            "license": he_ver_license,
            "heVersionSource": he_ver_source,
        }
        print(f"  {len(verses)} verses, {heb_count} with Hebrew")
        time.sleep(0.4)

    out = {
        "book_code": "TOB",
        "book_name": "Tobit (Hebrew back-translation, Neubauer 1878)",
        "source_url": "https://www.sefaria.org/",
        "fetched_at": dt.date.today().isoformat(),
        "note": (
            "Sefaria-hosted Public Domain Hebrew text. This is Adolf "
            "Neubauer's 1878 back-translation from the Aramaic "
            "manuscript he edited, not an ancient Hebrew witness. The "
            "actual ancient evidence is Qumran 4Q196-200 (Aramaic), "
            "published in DJD XIX (commercial, not redistributable). "
            "Use this for translation reference only."
        ),
        "chapters": chapters,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_PATH}")
    total = sum(len(c["verses"]) for c in chapters.values())
    heb = sum(c["hebrew_count"] for c in chapters.values())
    print(f"  total: {total} verses, {heb} with Hebrew ({heb/total*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
