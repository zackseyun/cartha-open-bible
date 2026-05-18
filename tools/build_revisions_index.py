#!/usr/bin/env python3
"""build_revisions_index.py — walk every verse YAML and emit a
structured revisions index that the cartha.website frontend can fetch.

Output: `revisions.json` at repo root, served via GitHub raw CDN just
like `status.json`. Schema v3:

{
  "generated_at": "...",
  "commit_sha": "...",         # HEAD at generation time
  "schema_version": 1,
  "totals": {
    "verses_with_revisions": N,
    "total_revisions": M,       # can be > verses if one verse revised twice
    "by_category": {...},
    "by_tier": {...},
    "by_adjudicator": {...},
    "by_reviewer_model": {...},
    "by_credit_source": {...},
    "by_proposal_source": {...},
    "credited_contributors": N,
    "approved_credited_revisions": N,
    "public_proposals_accepted": N,
    "approved_significant_revisions": N,
    "approved_proposed_revisions": N,  # backwards-compatible alias
    "approved_community_revisions": N
  },
  "by_book": {
    "<slug>": {
      "display": "Genesis",
      "testament": "ot",
      "verse_count": N,
      "revision_count": M
    }
  },
  "revisions": [
    {
      "id": "GEN.3.4",
      "testament": "ot",
      "book_slug": "genesis",
      "book_display": "Genesis",
      "chapter": 3,
      "verse": 4,
      "timestamp": "2026-04-20T08:29:57Z",
      "adjudicator": "claude-opus-4-7",
      "reviewer_model": "gemini-2.5-pro",
      "category": "mistranslation",
      "tier": 2,
      "from": "You will not surely die.",
      "to": "You will surely not die.",
      "rationale": "Hebrew לֹא מוֹת...",
      "source_review": "state/reviews/gemini/...",
      "credit": {"source": "community", "display_name": "..."}
    },
    ...
  ]
}
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
REVIEWS_ROOT = REPO_ROOT / "state" / "reviews"
OUT_PATH = REPO_ROOT / "revisions.json"
# Bumped to 2 when the review_coverage block was added. The block
# captures every review pass we ran (one record per verse per
# reviewer), independent of whether the pass produced an applied
# edit. Without it the public count missed every "agree" verdict —
# i.e., the majority of the work — and made it look like only ~9%
# of verses had been touched. The frontend should treat the absence
# of review_coverage as "old snapshot, only applied-edit counts
# available" and fall back gracefully.
#
# Bumped to 3 when optional contributor-credit metadata was added.
# A revision can now carry one of:
#   credit: {source, display_name, account_id?, issue_url?}
#   contributor: {source, display_name, account_id?, issue_url?}
#   suggested_by: <string-or-dict>
# The index passes that metadata through and aggregates it so public
# clients can distinguish approved, significant proposals from the
# larger machine-assisted applied-edit log. "Approved" is intentionally
# narrower than "all applied": explicit reader/maintainer proposals,
# tier-2/tier-3 source-grounded findings in material categories, and
# high-impact repair passes (source correction, verse-boundary redraft,
# truncation/regression repair, doctrine realignment, theological
# weight, stacked review).
SCHEMA_VERSION = 3
SUMMARY_OUT_PATH = REPO_ROOT / "revisions-summary.json"

PROPOSAL_ADJUDICATORS = {
    "human",
    "human-maintainer",
    "maintainer",
}

PUBLIC_PROPOSAL_SOURCES = {
    "public",
    "community",
    "contributor",
    "human",
    "human-maintainer",
    "human_maintainer",
    "maintainer",
    "reader",
    "reader_suggestion",
}

SIGNIFICANT_APPROVED_TIER_CATEGORIES = {
    "mistranslation",
    "lexical",
    "missing_nuance",
    "source_correction",
    "theological_weight",
    "theological_clarity",
    "doctrine_realignment",
    "consistency_or_metadata_alignment",
}

SIGNIFICANT_APPROVED_REPAIR_CATEGORIES = {
    "source_correction",
    "verse_boundary_redraft",
    "theological_weight",
    "doctrine_realignment",
    "truncation_fix",
    "regression_fix",
    "stacked_review",
}

# 3-letter codes (SBL / Paratext style) keyed by slug — drives the
# canonical_id prefix (GEN, EXO, ...) and provides display names.
BOOK_META: dict[str, tuple[str, str, str]] = {
    # testament, slug, display name, sbl_code
    "ot": {
        "genesis": ("Genesis", "GEN"), "exodus": ("Exodus", "EXO"),
        "leviticus": ("Leviticus", "LEV"), "numbers": ("Numbers", "NUM"),
        "deuteronomy": ("Deuteronomy", "DEU"), "joshua": ("Joshua", "JOS"),
        "judges": ("Judges", "JDG"), "ruth": ("Ruth", "RUT"),
        "1_samuel": ("1 Samuel", "1SA"), "2_samuel": ("2 Samuel", "2SA"),
        "1_kings": ("1 Kings", "1KI"), "2_kings": ("2 Kings", "2KI"),
        "1_chronicles": ("1 Chronicles", "1CH"),
        "2_chronicles": ("2 Chronicles", "2CH"),
        "ezra": ("Ezra", "EZR"), "nehemiah": ("Nehemiah", "NEH"),
        "esther": ("Esther", "EST"), "job": ("Job", "JOB"),
        "psalms": ("Psalms", "PSA"), "proverbs": ("Proverbs", "PRO"),
        "ecclesiastes": ("Ecclesiastes", "ECC"),
        "song_of_songs": ("Song of Songs", "SNG"),
        "isaiah": ("Isaiah", "ISA"), "jeremiah": ("Jeremiah", "JER"),
        "lamentations": ("Lamentations", "LAM"),
        "ezekiel": ("Ezekiel", "EZK"), "daniel": ("Daniel", "DAN"),
        "hosea": ("Hosea", "HOS"), "joel": ("Joel", "JOL"),
        "amos": ("Amos", "AMO"), "obadiah": ("Obadiah", "OBA"),
        "jonah": ("Jonah", "JON"), "micah": ("Micah", "MIC"),
        "nahum": ("Nahum", "NAM"), "habakkuk": ("Habakkuk", "HAB"),
        "zephaniah": ("Zephaniah", "ZEP"), "haggai": ("Haggai", "HAG"),
        "zechariah": ("Zechariah", "ZEC"), "malachi": ("Malachi", "MAL"),
    },
    "nt": {
        "matthew": ("Matthew", "MAT"), "mark": ("Mark", "MRK"),
        "luke": ("Luke", "LUK"), "john": ("John", "JHN"),
        "acts": ("Acts", "ACT"), "romans": ("Romans", "ROM"),
        "1_corinthians": ("1 Corinthians", "1CO"),
        "2_corinthians": ("2 Corinthians", "2CO"),
        "galatians": ("Galatians", "GAL"),
        "ephesians": ("Ephesians", "EPH"),
        "philippians": ("Philippians", "PHP"),
        "colossians": ("Colossians", "COL"),
        "1_thessalonians": ("1 Thessalonians", "1TH"),
        "2_thessalonians": ("2 Thessalonians", "2TH"),
        "1_timothy": ("1 Timothy", "1TI"),
        "2_timothy": ("2 Timothy", "2TI"),
        "titus": ("Titus", "TIT"), "philemon": ("Philemon", "PHM"),
        "hebrews": ("Hebrews", "HEB"), "james": ("James", "JAS"),
        "1_peter": ("1 Peter", "1PE"), "2_peter": ("2 Peter", "2PE"),
        "1_john": ("1 John", "1JN"), "2_john": ("2 John", "2JN"),
        "3_john": ("3 John", "3JN"), "jude": ("Jude", "JUD"),
        "revelation": ("Revelation", "REV"),
    },
    "deuterocanon": {
        meta[4]: (meta[3], code)
        for code, meta in lxx_swete.DEUTEROCANONICAL_BOOKS.items()
    },
}


def head_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return ""


def display_name_for(book_slug: str, testament: str) -> tuple[str, str]:
    t = BOOK_META.get(testament, {}).get(book_slug)
    if t:
        return t
    return book_slug.replace("_", " ").title(), book_slug.upper()[:3]


def normalize_credit(rev: dict[str, Any]) -> dict[str, Any] | None:
    """Return optional public contributor credit for a revision.

    This is intentionally permissive because the approved-revision YAML
    may be edited by humans during adjudication. The public website only
    needs stable display metadata; private account details should be
    omitted unless a maintainer deliberately chooses to expose them.
    """
    raw = (
        rev.get("credit")
        or rev.get("contributor")
        or rev.get("suggested_by")
    )
    if not raw:
        return None

    if isinstance(raw, str):
        display = raw.strip()
        if not display:
            return None
        return {
            "source": "community",
            "display_name": display,
        }

    if not isinstance(raw, dict):
        return None

    display = (
        raw.get("display_name")
        or raw.get("name")
        or raw.get("credit")
        or raw.get("public_name")
        or ""
    )
    display = str(display).strip()
    if not display:
        return None

    source = str(raw.get("source") or "community").strip() or "community"
    out: dict[str, Any] = {
        "source": source,
        "display_name": display,
    }
    for key in ("account_id", "issue_url", "submitted_at", "approved_at", "profile_url"):
        value = raw.get(key)
        if value:
            out[key] = value
    return out


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "approved"}
    return False


def proposal_source_for(rev: dict[str, Any], credit: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Classify significant approved revisions for the public badge.

    This deliberately does not count every applied edit. It counts:
      - explicit public credits / suggestions,
      - explicit approved_revision / approved_proposal flags,
      - human/maintainer adjudications,
      - material tier-2/tier-3 source-grounded categories,
      - high-impact repair categories even when no tier was recorded.

    Returns: (source, reason) or (None, None).
    """
    if credit:
        return str(credit.get("source") or "community").strip() or "community", "explicit_credit"

    explicit_source = str(
        rev.get("proposal_source")
        or rev.get("approved_revision_source")
        or rev.get("approved_source")
        or ""
    ).strip()
    if explicit_source:
        return explicit_source, "explicit_source"

    if _truthy(rev.get("approved_revision")) or _truthy(rev.get("approved_proposal")):
        return "maintainer", "explicit_flag"

    adjudicator = str(rev.get("adjudicator") or "").strip().lower()
    if adjudicator in PROPOSAL_ADJUDICATORS or "maintainer" in adjudicator:
        return "maintainer", "human_or_maintainer"

    category = str(rev.get("category") or "").strip()
    tier = str(rev.get("tier") or "").strip()
    if tier in {"2", "3"} and category in SIGNIFICANT_APPROVED_TIER_CATEGORIES:
        return "source_grounded_review", "tier2_3_source_grounded"
    if category in SIGNIFICANT_APPROVED_REPAIR_CATEGORIES:
        return "source_grounded_review", "major_repair"
    return None, None


def walk_verses() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not TRANSLATION_ROOT.exists():
        return out
    for testament_dir in TRANSLATION_ROOT.iterdir():
        if not testament_dir.is_dir():
            continue
        testament = testament_dir.name
        for book_dir in testament_dir.iterdir():
            if not book_dir.is_dir():
                continue
            book_slug = book_dir.name
            display, sbl_code = display_name_for(book_slug, testament)
            for chapter_dir in book_dir.iterdir():
                if not chapter_dir.is_dir():
                    continue
                try:
                    chapter_num = int(chapter_dir.name)
                except ValueError:
                    continue
                for yaml_path in chapter_dir.glob("*.yaml"):
                    try:
                        verse_num = int(yaml_path.stem)
                    except ValueError:
                        continue
                    try:
                        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    revs = data.get("revisions") or []
                    if not revs:
                        continue
                    for rev in revs:
                        if not isinstance(rev, dict):
                            continue
                        item = {
                            "id": f"{sbl_code}.{chapter_num}.{verse_num}",
                            "testament": testament,
                            "book_slug": book_slug,
                            "book_display": display,
                            "chapter": chapter_num,
                            "verse": verse_num,
                            "timestamp": rev.get("timestamp"),
                            "adjudicator": rev.get("adjudicator"),
                            "reviewer_model": rev.get("reviewer_model"),
                            "category": rev.get("category"),
                            "tier": rev.get("tier"),
                            "from": rev.get("from"),
                            "to": rev.get("to"),
                            "rationale": rev.get("rationale"),
                            "source_review": rev.get("source_review"),
                        }
                        credit = normalize_credit(rev)
                        if credit:
                            item["credit"] = credit
                        proposal_source, approval_reason = proposal_source_for(rev, credit)
                        if proposal_source:
                            item["approved_proposal"] = True
                            item["proposal_source"] = proposal_source
                            item["approval_reason"] = approval_reason
                        out.append(item)
    return out


# Reviewer-model name prefixes that count as the original drafter
# (NOT as independent eyes). A revision_pass block whose model starts
# with one of these is the drafter self-checking, not a second model.
DRAFTER_MODEL_PREFIXES: tuple[str, ...] = ("gpt-5", "gpt-4")


def _is_independent_reviewer(model_name: str) -> bool:
    """True if a model name represents an independent reviewer (Azure /
    Gemini / Claude / etc.), False if it's the original drafter
    self-pass. Used so the verses_reviewed count includes Azure
    revision-pass and future Vertex Gemini work even when those land
    in the verse YAML rather than state/reviews/."""
    if not model_name:
        return False
    name = model_name.lower()
    if any(name.startswith(p) for p in DRAFTER_MODEL_PREFIXES):
        return False
    return True


def walk_yaml_independent_reviews() -> dict[tuple[str, str], set[str]]:
    """Walk verse YAMLs for independent revision-pass evidence.

    A verse counts as "independently reviewed" if EITHER:
      - its `revision_pass.model` is non-drafter (Azure, Gemini, Claude…), OR
      - its `revisions:` array contains an entry whose adjudicator or
        reviewer_model is non-drafter.

    Returns: {(testament, slug): {verse_id, ...}} of distinct verses
    with independent YAML evidence. The keys mirror the layout used by
    walk_review_records() so the two can be unioned downstream.

    Slow walk (~few-min on Google Drive) but produces nothing the
    maintainer machine can't already cache. Skipped when translation/
    is missing.
    """
    out: dict[tuple[str, str], set[str]] = {}
    if not TRANSLATION_ROOT.exists():
        return out
    for testament_dir in TRANSLATION_ROOT.iterdir():
        if not testament_dir.is_dir():
            continue
        testament = testament_dir.name
        for book_dir in testament_dir.iterdir():
            if not book_dir.is_dir():
                continue
            slug = book_dir.name
            display, code = display_name_for(slug, testament)
            for chap_dir in book_dir.iterdir():
                if not chap_dir.is_dir() or not chap_dir.name.isdigit():
                    continue
                chap = int(chap_dir.name)
                for yp in chap_dir.glob("*.yaml"):
                    if not yp.stem.isdigit():
                        continue
                    verse = int(yp.stem)
                    try:
                        data = yaml.safe_load(yp.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    independent = False
                    rp = data.get("revision_pass") or {}
                    if isinstance(rp, dict) and _is_independent_reviewer(rp.get("model") or ""):
                        independent = True
                    if not independent:
                        for r in (data.get("revisions") or []):
                            if not isinstance(r, dict):
                                continue
                            if _is_independent_reviewer(r.get("adjudicator") or "") or _is_independent_reviewer(r.get("reviewer_model") or ""):
                                independent = True
                                break
                    if independent:
                        vid = f"{code}.{chap}.{verse}"
                        out.setdefault((testament, slug), set()).add(vid)
    return out


def walk_review_records() -> dict[str, Any]:
    """Aggregate state/reviews/**.json into a public coverage block.

    Each review file is one verse-level pass by a reviewer model and
    represents work done regardless of whether an edit was applied.
    state/ is gitignored, so this only produces meaningful output when
    run from a working tree that has the review records present (i.e.,
    locally on the maintainer's machine — see the launchd flywheel
    com.cartha.pob-revisions-flywheel.plist). When run on GitHub
    Actions the dir is empty and we return zeros, which is honest:
    the public snapshot is stale until the local flywheel pushes.

    Schema returned:
      {
        "verses_reviewed": int,           # distinct verse IDs (state/reviews ∪ YAML)
        "review_passes_total": int,        # total pass files (state/reviews only)
        "by_verdict": {verdict: count},
        "by_reviewer_model": {model: count},
        "by_strategy": {strategy: count},
        "by_book": {slug: {
            "display": str, "testament": str,
            "verses_reviewed": int, "passes": int}},
      }

    The verses_reviewed count UNIONS state/reviews/ with YAML
    revision_pass / revisions[] evidence from non-drafter models, so
    Azure GPT-5.4 revision passes and future Vertex Gemini reviews
    count even though they don't write to state/reviews/.
    """
    coverage: dict[str, Any] = {
        "verses_reviewed": 0,
        "review_passes_total": 0,
        "by_verdict": {},
        "by_reviewer_model": {},
        "by_strategy": {},
        "by_book": {},
    }
    if not REVIEWS_ROOT.exists():
        # Even with no state/reviews/, YAML evidence may exist.
        yaml_extra = walk_yaml_independent_reviews()
        if yaml_extra:
            by_book: dict[str, Any] = {}
            total_verses = 0
            for (testament, slug), verses in yaml_extra.items():
                display, _ = display_name_for(slug, testament)
                by_book[slug] = {
                    "display": display,
                    "testament": testament,
                    "verses_reviewed": len(verses),
                    "passes": len(verses),
                }
                total_verses += len(verses)
            coverage.update({
                "verses_reviewed": total_verses,
                "by_book": by_book,
            })
        return coverage

    by_verdict: Counter = Counter()
    by_reviewer: Counter = Counter()
    by_strategy: Counter = Counter()
    by_book_slug: dict[str, dict[str, Any]] = {}
    distinct_verses: set[str] = set()
    passes_total = 0

    for jf in REVIEWS_ROOT.rglob("*.json"):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        vid = data.get("id")
        if not vid:
            # Older Didache/2 Esdras records use chapter-only ids; skip
            # for now — they're double-covered by per-verse reviews on
            # the same passages.
            continue
        passes_total += 1
        by_verdict[data.get("verdict") or "unknown"] += 1
        by_reviewer[data.get("reviewer_model") or "unknown"] += 1
        by_strategy[data.get("strategy") or "unknown"] += 1
        distinct_verses.add(vid)

        slug = data.get("book_slug") or vid.split(".")[0].lower()
        testament = data.get("testament") or "unknown"
        display, _code = display_name_for(slug, testament) if testament in BOOK_META else (slug.replace("_", " ").title(), slug.upper()[:3])
        info = by_book_slug.setdefault(slug, {
            "display": display,
            "testament": testament,
            "passes": 0,
            "_distinct_verses": set(),
        })
        info["passes"] += 1
        info["_distinct_verses"].add(vid)

    # Union with YAML-side independent revision evidence (Azure
    # GPT-5.4, future Vertex Gemini, Claude adjudications…). Without
    # this, ~18k verses where Azure landed an applied revision but no
    # state/reviews/ entry exists would be undercounted as not
    # reviewed even though they have independent eyes recorded in the
    # YAML.
    yaml_extra = walk_yaml_independent_reviews()
    yaml_only_verses_added = 0
    for (testament, slug), verses in yaml_extra.items():
        info = by_book_slug.setdefault(slug, {
            "display": display_name_for(slug, testament)[0] if testament in BOOK_META else slug.replace("_", " ").title(),
            "testament": testament,
            "passes": 0,
            "_distinct_verses": set(),
        })
        # state/reviews ids are lowercase ("matthew.1.1") and YAML
        # extras are 3-letter-code uppercase ("MAT.1.1"). Normalize
        # both into the per-book set so we don't double-count.
        existing_norm = {
            v.split(".", 1)[1] if "." in v else v
            for v in info["_distinct_verses"]
        }
        for vid in verses:
            tail = vid.split(".", 1)[1] if "." in vid else vid
            if tail not in existing_norm:
                info["_distinct_verses"].add(vid)
                existing_norm.add(tail)
                yaml_only_verses_added += 1
                distinct_verses.add(vid)

    by_book: dict[str, Any] = {}
    for slug, info in by_book_slug.items():
        by_book[slug] = {
            "display": info["display"],
            "testament": info["testament"],
            "verses_reviewed": len(info["_distinct_verses"]),
            "passes": info["passes"],
        }

    coverage.update({
        "verses_reviewed": len(distinct_verses),
        "review_passes_total": passes_total,
        "by_verdict": dict(by_verdict),
        "by_reviewer_model": dict(by_reviewer),
        "by_strategy": dict(by_strategy),
        "by_book": by_book,
        "yaml_only_verses_added": yaml_only_verses_added,
    })
    return coverage


def build_index() -> dict[str, Any]:
    revisions = walk_verses()
    # Sort newest first
    revisions.sort(key=lambda r: r.get("timestamp") or "", reverse=True)

    by_category: Counter = Counter()
    by_tier: Counter = Counter()
    by_adjudicator: Counter = Counter()
    by_reviewer: Counter = Counter()
    by_credit_source: Counter = Counter()
    by_proposal_source: Counter = Counter()
    credited_contributors: set[str] = set()
    by_book_slug: dict[str, dict[str, Any]] = {}
    verse_ids: set[str] = set()

    for rev in revisions:
        by_category[rev.get("category") or "other"] += 1
        tier = rev.get("tier")
        if tier is not None:
            by_tier[str(tier)] += 1
        by_adjudicator[rev.get("adjudicator") or "unknown"] += 1
        by_reviewer[rev.get("reviewer_model") or "unknown"] += 1
        credit = rev.get("credit") if isinstance(rev.get("credit"), dict) else None
        if credit:
            source = credit.get("source") or "community"
            by_credit_source[source] += 1
            display_name = credit.get("display_name")
            if display_name:
                credited_contributors.add(str(display_name))
        proposal_source = rev.get("proposal_source")
        if proposal_source:
            by_proposal_source[str(proposal_source)] += 1
        slug = rev["book_slug"]
        info = by_book_slug.setdefault(slug, {
            "display": rev["book_display"],
            "testament": rev["testament"],
            "verse_count": 0,  # distinct verses
            "revision_count": 0,
            "distinct_verses": set(),
        })
        info["revision_count"] += 1
        info["distinct_verses"].add(rev["id"])
        verse_ids.add(rev["id"])

    # Finalize book metadata
    by_book: dict[str, Any] = {}
    for slug, info in by_book_slug.items():
        by_book[slug] = {
            "display": info["display"],
            "testament": info["testament"],
            "verse_count": len(info["distinct_verses"]),
            "revision_count": info["revision_count"],
        }

    review_coverage = walk_review_records()

    # If state/reviews/ is empty (e.g. running on GitHub Actions where
    # state/ is gitignored and absent), don't blow away the
    # review_coverage block that the local flywheel last published.
    # The block is only authoritative when produced from a tree that
    # actually has the review records; otherwise we'd be overwriting
    # 50k+ data points with zeros and the page would lie again.
    if review_coverage["review_passes_total"] == 0 and OUT_PATH.exists():
        try:
            prior = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            prior_coverage = prior.get("review_coverage")
            if prior_coverage and prior_coverage.get("review_passes_total", 0) > 0:
                review_coverage = prior_coverage
                review_coverage["preserved_from_prior_snapshot"] = True
        except Exception:
            pass

    public_proposals_accepted = sum(
        count
        for source, count in by_proposal_source.items()
        if str(source).strip().lower() in PUBLIC_PROPOSAL_SOURCES
    )

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit_sha": head_commit_sha(),
        "schema_version": SCHEMA_VERSION,
        "totals": {
            "verses_with_revisions": len(verse_ids),
            "total_revisions": len(revisions),
            "by_category": dict(by_category),
            "by_tier": dict(by_tier),
            "by_adjudicator": dict(by_adjudicator),
            "by_reviewer_model": dict(by_reviewer),
            "by_credit_source": dict(by_credit_source),
            "by_proposal_source": dict(by_proposal_source),
            "credited_contributors": len(credited_contributors),
            "approved_credited_revisions": sum(by_credit_source.values()),
            "public_proposals_accepted": public_proposals_accepted,
            "accepted_public_proposals": public_proposals_accepted,
            "approved_public_proposals": public_proposals_accepted,
            "approved_significant_revisions": sum(by_proposal_source.values()),
            # Backwards-compatible aliases for deployed frontend builds that
            # still read the older proposal-oriented field names.
            "approved_proposed_revisions": sum(by_proposal_source.values()),
            "approved_human_proposed_revisions": sum(by_proposal_source.values()),
            "approved_source_grounded_revisions": by_proposal_source.get("source_grounded_review", 0),
            "approved_maintainer_revisions": by_proposal_source.get("maintainer", 0),
            "approved_community_revisions": by_credit_source.get("community", 0),
        },
        "review_coverage": review_coverage,
        "by_book": by_book,
        "revisions": revisions,
    }


def build_summary(index: dict[str, Any]) -> dict[str, Any]:
    """Small public summary for lightweight reader-page stats.

    `revisions.json` is intentionally detailed and can be large. The
    reader landing page only needs totals, so keep this file tiny and
    safe to fetch during normal browsing.
    """
    rc = index.get("review_coverage") or {}
    return {
        "generated_at": index.get("generated_at"),
        "commit_sha": index.get("commit_sha"),
        "schema_version": index.get("schema_version"),
        "totals": index.get("totals") or {},
        "review_coverage": {
            "verses_reviewed": rc.get("verses_reviewed", 0),
            "review_passes_total": rc.get("review_passes_total", 0),
            "by_verdict": rc.get("by_verdict") or {},
            "by_reviewer_model": rc.get("by_reviewer_model") or {},
            "preserved_from_prior_snapshot": rc.get("preserved_from_prior_snapshot", False),
        },
    }


def main() -> int:
    index = build_index()
    OUT_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_OUT_PATH.write_text(
        json.dumps(build_summary(index), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    t = index["totals"]
    rc = index["review_coverage"]
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {SUMMARY_OUT_PATH}")
    print(f"  applied edits: {t['total_revisions']} across {t['verses_with_revisions']} verses")
    print(f"  review passes: {rc['review_passes_total']} across {rc['verses_reviewed']} verses")
    print(f"  by_category: {t['by_category']}")
    print(f"  by_tier: {t['by_tier']}")
    print(f"  by_adjudicator: {t['by_adjudicator']}")
    print(f"  by_credit_source: {t['by_credit_source']}")
    print(f"  by_verdict: {rc['by_verdict']}")
    print(f"  books touched (applied): {len(index['by_book'])}")
    print(f"  books touched (reviewed): {len(rc['by_book'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
