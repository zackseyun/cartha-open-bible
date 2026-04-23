#!/usr/bin/env python3
"""fetch_psalm_151_hebrew.py — stage a local-only Psalm 151 Hebrew cache.

Fetches the 10-verse Hebrew Psalm 151 text from the Sefaria API and writes
it to the drafter's local reference workspace:

  ~/cartha-reference-local/psalm151_hebrew/psalm151_kahana_1937.json

This output is deliberately outside the repo because the Hebrew source is
treated as consult-only in the current COB policy.
"""
from __future__ import annotations

import json
import pathlib
import urllib.request
from datetime import datetime, timezone


API_URL = "https://www.sefaria.org/api/texts/Psalm_151?lang=he&context=0&commentary=0"
OUT_DIR = pathlib.Path.home() / "cartha-reference-local" / "psalm151_hebrew"
OUT_PATH = OUT_DIR / "psalm151_kahana_1937.json"


def fetch() -> dict:
    req = urllib.request.Request(API_URL, headers={"User-Agent": "cartha-open-bible/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read().decode("utf-8"))

    verses = []
    heb = payload.get("he") or []
    eng = payload.get("text") or []
    for i, h in enumerate(heb, start=1):
        verses.append({
            "verse": i,
            "hebrew": h,
            "english": eng[i - 1] if i - 1 < len(eng) else "",
        })

    versions = payload.get("versions") or []
    he_version = next((v for v in versions if v.get("language") == "he"), {})
    return {
        "book_code": "PS151",
        "book_name": "Psalm 151 (Hebrew consult text)",
        "fetched_from": API_URL,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "versionTitle": he_version.get("versionTitle", ""),
        "versionSource": he_version.get("versionSource", ""),
        "license": he_version.get("license", "unknown"),
        "note": (
            "Local-only consult cache for the Hebrew 10-verse Psalm 151 form. "
            "Not vendored into the repo; use as Zone 2 consult only."
        ),
        "verses": verses,
    }


def main() -> int:
    data = fetch()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Verses: {len(data['verses'])}")
    print(f"Version: {data.get('versionTitle','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
