"""Parse the CopticScriptorium (Dilley 2025) TEI edition of the Gospel of
Thomas into one JSONL record per saying.

Source: https://github.com/CopticScriptorium/corpora → thomas-gospel/
License: CC-BY 4.0 (asserted in TEI header)
Manuscript: NHAM 02 (Nag Hammadi Codex II), pp. 32–51.

TEI structure in this file:
    <div1 n="N">                       # saying (or "subtitle")
      <p n="M">
        <s style="...">
          <lb n="K"/>                  # line break (numbers are absolute within codex page)
          <phr>
            <w type="..." lemma="...">ⲙⲟⲣⲡⲏⲙⲉ</w>
            <w type="..." lemma="...">ⲁ</w>
          </phr>
          ...
        </s>
      </p>
    </div1>

Multiple <w> children inside one <phr> are morphemes of a single printed word,
so we join them without spaces. Phrases are separated by a single space —
closely tracking how scholarly editions (Layton 1989, Bethge et al. 1996) print
the text.

Output record shape:
    {
      "saying_id": "000" | "001" ... "114" | "subtitle",
      "div1_n": "0" | "1" ... | "subtitle",
      "label": "Incipit" | "Saying 1" ... | "Subtitle",
      "coptic_orig": "ⲛⲁⲉⲓ ⲛⲉ ⲛ̄ϣⲁϫⲉ ...",       # printed form (phr-joined morphemes)
      "coptic_norm": "ⲡⲁⲓ ⲡⲉ ⲡϣⲁϫⲉ ...",        # lemmatized / normalized Sahidic
      "lines": [
        {"lb": "1", "codex_page": "NHAM02.32", "orig": "...", "norm": "..."},
      ],
      "codex_pages": ["NHAM02.32", "NHAM02.33"],
      "source": {
        "edition": "Dilley 2025 (Coptic Scriptorium v6.2.0)",
        "license": "CC-BY 4.0",
        "tei_urn": "urn:cts:copticLit:nh.thomas.NHAM02:0-114"
      }
    }
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
TEI_PATH = Path(
    "sources/nag_hammadi/raw/gospel_of_thomas/coptic_scriptorium_thomas.tei.xml"
)
OUT_PATH = Path("sources/nag_hammadi/texts/gospel_of_thomas/coptic.jsonl")
LICENSE_URN = "urn:cts:copticLit:nh.thomas.NHAM02:0-114"


def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[-1]


def _t(s: str | None) -> str:
    return "".join((s or "").split())


def _flatten_nonbreak_text(node: ET.Element) -> str:
    """Collect node text recursively while skipping break tags."""
    parts: list[str] = []

    def visit(el: ET.Element) -> None:
        if _tag(el) not in {"lb", "pb"}:
            txt = _t(el.text)
            if txt:
                parts.append(txt)
        for child in el:
            if _tag(child) not in {"lb", "pb"}:
                visit(child)
            tail = _t(child.tail)
            if tail:
                parts.append(tail)

    visit(node)
    return "".join(parts)


def _phrase_norm(phr: ET.Element) -> str:
    """Return the normalized / lemmatized form for one <phr>."""
    norms: list[str] = []
    for w in phr.iter():
        if _tag(w) != "w":
            continue
        tok = _flatten_nonbreak_text(w)
        if not tok:
            continue
        lemma = w.get("lemma")
        norms.append(lemma if lemma else tok)
    return "".join(norms)


def _phrase_segments(
    phr: ET.Element,
    *,
    current_page: str,
    current_lb: str | None,
    pages_seen: list[str],
) -> tuple[list[dict[str, str]], str, str | None]:
    """Split one printed phrase into per-line/page orig segments.

    The TEI often inserts `<lb/>` inside a `<w>` or even inside a morpheme, so we
    cannot line-split by phrase boundaries alone. Instead we walk the phrase in
    document order and emit a new segment whenever the page or line changes.
    """

    page_now = current_page
    lb_now = current_lb
    parts: list[dict[str, str]] = []
    buf = ""

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        parts.append(
            {
                "codex_page": page_now,
                "lb": lb_now or "",
                "orig": buf,
            }
        )
        buf = ""

    def add_text(text: str | None) -> None:
        nonlocal buf
        clean = _t(text)
        if clean:
            buf += clean

    def visit(el: ET.Element) -> None:
        nonlocal page_now, lb_now
        if _tag(el) not in {"lb", "pb"}:
            add_text(el.text)
        for child in el:
            tag = _tag(child)
            if tag == "pb":
                flush()
                pid = child.get(XML_ID) or page_now
                page_now = pid
                if pid and pid not in pages_seen:
                    pages_seen.append(pid)
            elif tag == "lb":
                flush()
                lb_now = child.get("n") or lb_now
            else:
                visit(child)
            add_text(child.tail)

    visit(phr)
    flush()
    return parts, page_now, lb_now


def _walk_saying(div1: ET.Element, current_page: str, current_lb: str | None) -> dict:
    pages: list[str] = []
    if current_page:
        pages.append(current_page)
    page_now = current_page
    lb_now: str | None = current_lb
    # Collect per (lb, page) line records in document order
    line_records: list[dict] = []
    line_key_idx: dict[tuple[str, str], int] = {}
    coptic_orig_parts: list[str] = []
    coptic_norm_parts: list[str] = []

    def _touch_line(lb: str | None, page: str) -> dict:
        key = (lb or "", page)
        if key not in line_key_idx:
            rec = {"lb": lb or "", "codex_page": page, "orig": [], "norm": []}
            line_key_idx[key] = len(line_records)
            line_records.append(rec)
        return line_records[line_key_idx[key]]

    def visit_container(node: ET.Element) -> None:
        nonlocal page_now, lb_now
        for child in node:
            tag = _tag(child)
            if tag == "pb":
                pid = child.get(XML_ID) or page_now
                page_now = pid
                if pid and pid not in pages:
                    pages.append(pid)
            elif tag == "lb":
                lb_now = child.get("n") or lb_now
            elif tag == "phr":
                segments, page_now, lb_now = _phrase_segments(
                    child,
                    current_page=page_now,
                    current_lb=lb_now,
                    pages_seen=pages,
                )
                norm = _phrase_norm(child)
                orig = "".join(seg["orig"] for seg in segments if seg["orig"])
                if orig:
                    coptic_orig_parts.append(orig)
                if norm:
                    coptic_norm_parts.append(norm)
                for idx, seg in enumerate(segments):
                    rec = _touch_line(seg["lb"] or lb_now, seg["codex_page"])
                    if seg["orig"]:
                        rec["orig"].append(seg["orig"])
                    if idx == 0 and norm:
                        rec["norm"].append(norm)
            else:
                visit_container(child)

    visit_container(div1)

    out_lines = [
        {
            "lb": r["lb"] or "?",
            "codex_page": r["codex_page"],
            "orig": " ".join(tok for tok in r["orig"] if tok),
            "norm": " ".join(tok for tok in r["norm"] if tok),
        }
        for r in line_records
        if any(r["orig"]) or any(r["norm"])
    ]

    coptic_orig = " ".join(coptic_orig_parts)
    coptic_norm = " ".join(coptic_norm_parts)
    return {
        "coptic_orig": coptic_orig,
        "coptic_norm": coptic_norm,
        "lines": out_lines,
        "codex_pages": pages,
        "_last_page": page_now,
        "_last_lb": lb_now,
    }


def iter_sayings(tei_path: Path) -> Iterator[dict]:
    """Walk the TEI in document order tracking page context across div1 boundaries."""
    tree = ET.parse(tei_path)
    root = tree.getroot()
    body = root.find(".//tei:body", NS)
    if body is None:
        raise SystemExit("No <body> found in TEI")
    # First pass: walk children of body in order, tracking the current page
    # so that when we enter a div1, we know which codex page it starts on.
    current_page = ""
    current_lb: str | None = None
    for child in body:
        tag = _tag(child)
        if tag == "pb":
            pid = child.get(XML_ID) or ""
            if pid:
                current_page = pid
        elif tag == "lb":
            current_lb = child.get("n") or current_lb
        elif tag == "div1":
            n = child.get("n") or ""
            if n == "subtitle":
                saying_id = "subtitle"
                label = "Subtitle"
            else:
                try:
                    as_int = int(n)
                    saying_id = f"{as_int:03d}"
                    label = "Incipit" if as_int == 0 else f"Saying {as_int}"
                except ValueError:
                    saying_id = n or "unknown"
                    label = n or "Unknown"
            data = _walk_saying(child, current_page, current_lb)
            # Advance the tracking page if this div1 crossed onto a new one
            last = data.pop("_last_page", "")
            if last:
                current_page = last
            last_lb = data.pop("_last_lb", None)
            if last_lb:
                current_lb = last_lb
            yield {
                "saying_id": saying_id,
                "div1_n": n,
                "label": label,
                "coptic_orig": data["coptic_orig"],
                "coptic_norm": data["coptic_norm"],
                "lines": data["lines"],
                "codex_pages": data["codex_pages"],
                "source": {
                    "edition": "Dilley 2025 (Coptic Scriptorium v6.2.0)",
                    "license": "CC-BY 4.0",
                    "tei_urn": LICENSE_URN,
                },
            }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tei", default=str(TEI_PATH))
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()
    tei = Path(args.tei)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    pages_hit: set[str] = set()
    with out.open("w", encoding="utf-8") as fh:
        for rec in iter_sayings(tei):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            pages_hit.update(rec["codex_pages"])
            count += 1
    print(
        f"wrote {count} sayings across {len(pages_hit)} codex pages -> {out}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
