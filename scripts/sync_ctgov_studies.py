"""Prewarm the on-disk per-NCT cache for every NCT ID cited in the KB.

Closes the data side of Gap 3 from `docs/reviews/ctgov-wiring-audit-2026-05-18.md`.
Sibling to `scripts/sync_ctgov_trials.py` — that one prewarms search-mode
queries (used by the experimental-options track); this one prewarms
get_trial-mode lookups (used by render-layer citation decoration).

What it does
------------

1. Walks `knowledge_base/hosted/content/sources/*.yaml` +
   `knowledge_base/hosted/content/indications/*.yaml`.
2. Extracts every NCT ID via regex (NCT IDs sit in free-text prose
   fields, not dedicated columns — see
   `knowledge_base.engine.citation_enrichment.extract_nct_ids`).
3. For each NCT not in cache (or past `--max-age`), calls
   `ctgov_client.get_trial(nct)` and writes the parsed dict to
   `knowledge_base/hosted/content/cache/ctgov_studies/<NCT>.json`.

Operational notes
-----------------

- `--dry-run` lists what would be fetched without making network calls.
  Safe to run anywhere; use it first before committing to a sync.
- `--sleep` (default 0.5 s) keeps us well under NLM's ~10 req/s soft
  cap. With ~200 unique NCTs that's a ~1.5 min walk.
- The cache directory is committed (per the same pattern as
  `cache/ctgov/`); run this script, review the diff, commit the cache.

Usage
-----

    python scripts/sync_ctgov_studies.py --dry-run
    python scripts/sync_ctgov_studies.py
    python scripts/sync_ctgov_studies.py --max-age-days 30 --sleep 0.3
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from knowledge_base.clients.ctgov_client import get_trial  # noqa: E402
from knowledge_base.engine.citation_enrichment import (  # noqa: E402
    DEFAULT_CACHE_ROOT,
    extract_nct_ids_from_files,
    load_study_from_cache,
    save_study_to_cache,
)


KB_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
SOURCE_DIR = KB_ROOT / "sources"
INDICATION_DIR = KB_ROOT / "indications"
CACHE_ROOT = REPO_ROOT / DEFAULT_CACHE_ROOT


def _yaml_files() -> list[Path]:
    return sorted(SOURCE_DIR.glob("*.yaml")) + sorted(INDICATION_DIR.glob("*.yaml"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the NCTs that would be fetched; no network calls.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Cache TTL — refresh entries older than this many days. "
             "Default 30. Pass 0 to refresh everything.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds to sleep between ctgov calls (default 0.5).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N NCTs (smoke testing).",
    )
    args = parser.parse_args()

    by_nct = extract_nct_ids_from_files(_yaml_files())
    print(f"[sync-ctgov-studies] {len(by_nct)} unique NCTs across "
          f"{sum(len(v) for v in by_nct.values())} citing entities.")

    if args.limit is not None:
        by_nct = dict(list(by_nct.items())[: args.limit])

    fresh = 0
    refreshed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []

    max_age = args.max_age_days if args.max_age_days > 0 else None

    for i, (nct, citing_files) in enumerate(sorted(by_nct.items()), start=1):
        cached = load_study_from_cache(nct, CACHE_ROOT, max_age_days=max_age)
        if cached is not None:
            skipped += 1
            continue

        prefix = "[would fetch]" if args.dry_run else f"[{i}/{len(by_nct)}]"
        print(f"  {prefix} {nct} (cited by {len(citing_files)})")

        if args.dry_run:
            continue

        try:
            study = get_trial(nct)
        except Exception as exc:  # noqa: BLE001 — record + continue
            failed.append((nct, str(exc)))
            continue

        if not study:
            failed.append((nct, "get_trial returned empty"))
            continue

        save_study_to_cache(nct, study, cache_root=CACHE_ROOT)
        if cached is None:
            fresh += 1
        else:
            refreshed += 1

        if args.sleep > 0:
            time.sleep(args.sleep)

    print(f"[sync-ctgov-studies] cache root: {CACHE_ROOT}")
    print(f"[sync-ctgov-studies] fresh: {fresh}, refreshed: {refreshed}, "
          f"skipped (within TTL): {skipped}, failed: {len(failed)}")
    if failed:
        print(f"[sync-ctgov-studies] failures:")
        for nct, err in failed[:10]:
            print(f"    {nct}: {err}")
        if len(failed) > 10:
            print(f"    … and {len(failed) - 10} more")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
