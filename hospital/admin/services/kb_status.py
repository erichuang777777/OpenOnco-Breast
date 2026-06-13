"""Read-only knowledge-base ingestion/verification status.

Powers the audit interface (task 3): surfaces, for clinical reviewers, the
state of imported guideline content without running the full validator —
entity counts per type, CIViC snapshot freshness, and source-citation
staleness (the §9 "sources older than 6 months enter the audit queue" rule
from SOURCE_INGESTION_SPEC).

Everything here is derived from the YAML on disk; nothing mutates the KB.
"""

from __future__ import annotations

import functools
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# Staleness threshold for source citations (SOURCE_INGESTION_SPEC §9: 6 months).
STALE_AFTER_DAYS = 183

# Entity directories surfaced as "content counts" in the audit dashboard.
_CONTENT_DIRS = [
    "algorithms",
    "diseases",
    "indications",
    "regimens",
    "redflags",
    "biomarkers",
    "biomarker_actionability",
    "drugs",
    "sources",
    "contraindications",
    "monitoring",
    "supportive_care",
    "procedures",
    "radiation_courses",
    "tests",
]


def _count_yaml(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.rglob("*.yaml"))


def _parse_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _source_freshness(sources_dir: Path, today: date) -> dict:
    """Scan source YAMLs for the most recent verification date and bucket
    them into fresh / stale / undated."""
    total = 0
    stale = 0
    undated = 0
    stalest: list[dict] = []
    if not sources_dir.is_dir():
        return {"total": 0, "stale": 0, "undated": 0, "stalest": []}
    for path in sources_dir.rglob("*.yaml"):
        try:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        total += 1
        verified = (
            _parse_date(data.get("last_verified"))
            or _parse_date(data.get("current_as_of"))
            or _parse_date(data.get("last_reviewed"))
        )
        if verified is None:
            undated += 1
            continue
        age = (today - verified).days
        if age > STALE_AFTER_DAYS:
            stale += 1
            stalest.append({
                "source_id": data.get("id", path.stem.upper()),
                "title": data.get("title"),
                "last_verified": verified.isoformat(),
                "age_days": age,
            })
    stalest.sort(key=lambda s: s["age_days"], reverse=True)
    return {"total": total, "stale": stale, "undated": undated, "stalest": stalest[:25]}


def _civic_snapshots(civic_root: Path) -> list[dict]:
    if not civic_root.is_dir():
        return []
    snapshots: list[dict] = []
    for child in sorted(civic_root.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        snap_date = _parse_date(child.name)
        evidence = child / "evidence.yaml"
        snapshots.append({
            "date": child.name,
            "iso_date": snap_date.isoformat() if snap_date else None,
            "has_evidence": evidence.is_file(),
        })
    return snapshots


@functools.lru_cache(maxsize=8)
def _compute_cached(kb_root_str: str, today_str: str) -> dict:
    kb_root = Path(kb_root_str)
    today = date.fromisoformat(today_str)

    content_counts = {name: _count_yaml(kb_root / name) for name in _CONTENT_DIRS}

    # CIViC snapshots live alongside `content/` under `hosted/civic/`.
    civic_root = kb_root.parent / "civic"
    snapshots = _civic_snapshots(civic_root)
    latest = snapshots[0] if snapshots else None
    civic_age_days = None
    if latest and latest["iso_date"]:
        civic_age_days = (today - date.fromisoformat(latest["iso_date"])).days

    freshness = _source_freshness(kb_root / "sources", today)

    return {
        "generated_at": today.isoformat(),
        "content_counts": content_counts,
        "total_entities": sum(content_counts.values()),
        "civic": {
            "snapshots": snapshots,
            "latest": latest,
            "latest_age_days": civic_age_days,
            "stale": civic_age_days is not None and civic_age_days > STALE_AFTER_DAYS,
        },
        "source_freshness": freshness,
        "stale_after_days": STALE_AFTER_DAYS,
    }


def compute_kb_status(kb_root: Path | str) -> dict:
    """Public entry point. Cached per (kb_root, calendar day)."""
    today = datetime.now(timezone.utc).date().isoformat()
    return _compute_cached(str(kb_root), today)
