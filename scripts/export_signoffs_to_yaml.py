#!/usr/bin/env python3
"""Export approved clinical sign-offs from the hospital DB into KB YAML.

Bridges the DB→YAML boundary: the clinical-review UI records two-reviewer
approvals in the hospital `kb_reviews` table, but the authoritative
`reviewer_signoffs` field lives in the versioned YAML (CHARTER §6.1). This
script turns each *approved* KbReview into identity-bearing ReviewerSignoff
entries on the corresponding entity.

It is deliberately conservative:
  * DRY-RUN by default — prints a plan and the exact YAML snippet per entity.
  * --apply edits only the top-level `reviewer_signoffs:` block (replace or
    append), preserving the rest of the file, then re-parses the YAML and
    reverts that file if parsing fails. It never runs git.
  * Reviewer ids: KbReview stores hospital user ids. Supply --reviewer-map
    (JSON {user_id: "REV-XXX"}) to emit canonical ReviewerProfile ids;
    without it the user id is written verbatim and a warning is printed.

After --apply, ALWAYS run `python scripts/audit_validator.py --human` and open
a reviewed PR — this script does not commit.

Usage:
    python scripts/export_signoffs_to_yaml.py [--db sqlite+aiosqlite:///./hospital.db]
        [--kb knowledge_base/hosted/content] [--reviewer-map map.json] [--apply]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import yaml

# type → content sub-directory (matches clinical_review service)
_TYPE_DIR = {
    "indication": "indications",
    "algorithm": "algorithms",
    "regimen": "regimens",
    "redflag": "redflags",
    "biomarker_actionability": "biomarker_actionability",
}


def _entity_file(kb_root: Path, etype: str, entity_id: str) -> Path | None:
    sub = _TYPE_DIR.get(etype)
    if not sub:
        return None
    base = kb_root / sub
    cand = base / (entity_id.strip().lower().replace("-", "_") + ".yaml")
    if cand.is_file():
        return cand
    matches = list(base.rglob(entity_id.strip().lower().replace("-", "_") + ".yaml"))
    return matches[0] if matches else None


def _signoff_entries(review, reviewer_map: dict[str, str]) -> list[dict]:
    out = []
    for who, when in (
        (review.reviewer_1, review.reviewer_1_at),
        (review.reviewer_2, review.reviewer_2_at),
    ):
        if not who:
            continue
        rid = reviewer_map.get(who, who)
        out.append({
            "reviewer_id": rid,
            "timestamp": (when.isoformat() if when else ""),
            "rationale": "Recorded via clinical-review UI sign-off.",
        })
    return out


def _render_block(entries: list[dict]) -> str:
    """Render the `reviewer_signoffs:` YAML block (2-space list indent)."""
    body = yaml.safe_dump(
        {"reviewer_signoffs": entries}, allow_unicode=True, sort_keys=False
    )
    return body.rstrip("\n")


def _set_block(text: str, entries: list[dict]) -> str:
    """Replace or append the top-level `reviewer_signoffs:` block."""
    block = _render_block(entries)
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("reviewer_signoffs:"):
            start = i
            break
    if start is None:
        sep = "" if text.endswith("\n") else "\n"
        return text + sep + block + "\n"
    # find end of the existing block: the key line + any indented continuation
    end = start + 1
    while end < len(lines) and (lines[end].startswith((" ", "\t")) or lines[end].strip() == ""):
        # stop at a blank line that precedes a new top-level key
        if lines[end].strip() == "" and end + 1 < len(lines) and lines[end + 1][:1] not in (" ", "\t", ""):
            break
        end += 1
    return "\n".join(lines[:start] + [block] + lines[end:])


async def _fetch_approved(db_url: str):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from hospital.db.models import KbReview

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        rows = list(await session.scalars(
            select(KbReview).where(KbReview.status == "approved")
        ))
    await engine.dispose()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./hospital.db"))
    ap.add_argument("--kb", default="knowledge_base/hosted/content")
    ap.add_argument("--reviewer-map", default=None, help="JSON {user_id: REV-id}")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    kb_root = Path(args.kb)
    reviewer_map: dict[str, str] = {}
    if args.reviewer_map:
        reviewer_map = json.loads(Path(args.reviewer_map).read_text(encoding="utf-8"))

    rows = asyncio.run(_fetch_approved(args.db))
    if not rows:
        print("No approved KbReviews to export.")
        return 0

    changed = warned = skipped = 0
    for r in rows:
        path = _entity_file(kb_root, r.entity_type, r.entity_id)
        if path is None:
            print(f"  SKIP {r.entity_type}/{r.entity_id}: YAML not found")
            skipped += 1
            continue
        entries = _signoff_entries(r, reviewer_map)
        if not reviewer_map and entries:
            warned += 1
        text = path.read_text(encoding="utf-8")
        new_text = _set_block(text, entries)

        print(f"\n=== {r.entity_type}/{r.entity_id}  ({path}) ===")
        print(_render_block(entries))
        if not reviewer_map:
            print("  ! reviewer_id written verbatim (no --reviewer-map; expected REV-* ids)")

        if args.apply:
            try:
                yaml.safe_load(new_text)  # re-parse guard
            except yaml.YAMLError as e:
                print(f"  ABORT write — would corrupt YAML: {e}")
                skipped += 1
                continue
            path.write_text(new_text, encoding="utf-8")
            changed += 1

    print(f"\n{'APPLIED' if args.apply else 'DRY-RUN'}: "
          f"{changed} written, {skipped} skipped, {warned} verbatim-reviewer warnings.")
    if not args.apply:
        print("Re-run with --apply to write. Then run audit_validator.py and open a reviewed PR.")
    elif changed:
        print("Next: python scripts/audit_validator.py --human  → then open a reviewed PR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
