"""NCT-ID enrichment for cited pivotal trials.

Closes Gap 3 from `docs/reviews/ctgov-wiring-audit-2026-05-18.md`. The
audit found:

- 147 NCT IDs across 144 `Source` entities (pivotal trial papers —
  KEYNOTE-024, CheckMate-067, ADAURA, etc.)
- 46 NCT IDs across 26 `Indication` entities

…all sitting in free-text `notes` / `summary` prose, never wired to
ctgov. This module is the data layer that lets a future render-layer
patch surface "NCT02220894 — status: COMPLETED" next to every pivotal
trial citation.

Architecture invariants
-----------------------

1. **Render-time only.** Per `CHARTER §8.3` and `SOURCE_INGESTION_SPEC`,
   ctgov data must never influence which Indication / Regimen the
   engine selects. Enrichment is decoration — read it, but never
   read it back as a routing signal.

2. **Cache-then-fetch.** The engine never calls upstream during render.
   `scripts/sync_ctgov_studies.py` populates the on-disk cache; the
   engine reads from it.

3. **Defensive across YAML schema evolution.** NCT IDs aren't in a
   dedicated field — they appear in `notes`, `summary`, `citation`
   prose. Extraction is regex over the JSON-serialized entity, which
   stays stable across YAML refactors.

Cache shape
-----------

One file per NCT ID at `<cache_root>/<NCT>.json`:

```json
{
  "cached_at": "2026-05-18T14:32:00+00:00",
  "study":     { "<parsed get_trial output>": ... }
}
```

Fresh-cutoff TTL is enforced by the caller (`sync_ctgov_studies.py`);
this module just reads what's on disk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional


_NCT_RE = re.compile(r"\bNCT\d{8}\b")


def extract_nct_ids(payload: object) -> list[str]:
    """Pull all NCT IDs out of a dict / list / string payload, deduped
    while preserving first-seen order.

    Walks any nested structure — works on raw YAML loads, schema model
    dumps, or hand-built dicts. NCT IDs typically sit in free-text
    `notes` / `summary` / `citation` fields, so the regex sweep is the
    most robust approach short of adding a dedicated `nct_ids: list[str]`
    field to every Source/Indication.

    Implementation note: we walk the structure recursively and regex
    each string leaf, rather than `json.dumps`-then-search the whole
    payload. The latter would false-negative when two NCTs sit on
    adjacent lines of a multi-line YAML string (json escapes the
    newline to `\\n`, putting the letter `n` immediately before the
    next `NCT`, which defeats the `\\b` word boundary).
    """
    if payload is None:
        return []
    seen: set[str] = set()
    out: list[str] = []
    _walk_for_ncts(payload, seen, out)
    return out


def _walk_for_ncts(node: object, seen: set[str], out: list[str]) -> None:
    if isinstance(node, str):
        for m in _NCT_RE.finditer(node):
            nct = m.group(0)
            if nct not in seen:
                seen.add(nct)
                out.append(nct)
        return
    if isinstance(node, dict):
        for v in node.values():
            _walk_for_ncts(v, seen, out)
        return
    if isinstance(node, (list, tuple, set)):
        for v in node:
            _walk_for_ncts(v, seen, out)
        return
    # ints, floats, bools, None, custom objects — nothing to scan


def extract_nct_ids_from_files(yaml_paths: Iterable[Path]) -> dict[str, list[str]]:
    """For a batch of YAML files, return `{nct_id: [file_basename, …]}`.

    Used by `sync_ctgov_studies.py` to know which entities reference
    each NCT — handy for the prewarm summary and for future cross-link
    rendering ("KEYNOTE-024 cited by 3 Indications").
    """
    import yaml as _yaml

    by_nct: dict[str, list[str]] = {}
    for path in yaml_paths:
        try:
            payload = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, _yaml.YAMLError):
            continue
        for nct in extract_nct_ids(payload):
            by_nct.setdefault(nct, []).append(path.name)
    return by_nct


# ── Cache I/O ────────────────────────────────────────────────────────────────

DEFAULT_CACHE_ROOT = Path("knowledge_base") / "hosted" / "content" / "cache" / "ctgov_studies"


def _cache_path(cache_root: Path, nct_id: str) -> Path:
    return Path(cache_root) / f"{nct_id}.json"


def load_study_from_cache(
    nct_id: str,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    *,
    max_age_days: Optional[int] = None,
) -> Optional[dict]:
    """Read the cached parsed-study dict for `nct_id`, or None if absent
    / unreadable / past `max_age_days`. Errors are swallowed — cache is
    a best-effort optimisation, never a correctness requirement.
    """
    path = _cache_path(cache_root, nct_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if max_age_days is not None:
        try:
            cached_at = datetime.fromisoformat(payload["cached_at"])
        except (KeyError, ValueError):
            return None
        if datetime.now(timezone.utc) - cached_at > timedelta(days=max_age_days):
            return None
    study = payload.get("study")
    return study if isinstance(study, dict) else None


def save_study_to_cache(
    nct_id: str,
    study: dict,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> Path:
    """Atomic-ish write: create parent, dump JSON, rename. Returns the
    final path. Errors propagate so the prewarm script can report
    failures."""
    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_root, nct_id)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "study": study,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


# ── Citation enrichment (consumed by future render-layer patch) ──────────────


@dataclass(frozen=True)
class TrialStatusBadge:
    """Minimal render-ready bundle for one cited NCT.

    Three fields are sufficient for the first render iteration:
    status string (`RECRUITING` / `COMPLETED` / etc.), whether the
    trial is still enrolling (drives badge colour), and last-synced
    date (drives "data may be stale" warning past 30 days).
    """

    nct_id: str
    status: str
    is_recruiting: bool
    last_synced: Optional[str] = None


_RECRUITING_STATUSES = frozenset({
    "RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
})


def trial_status_badge(
    nct_id: str,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> Optional[TrialStatusBadge]:
    """Build a `TrialStatusBadge` for the cached study, or None when
    the cache has nothing.

    Designed for render-time use. Render layer can call this per cited
    NCT ID and drop the result into the citation HTML.
    """
    study = load_study_from_cache(nct_id, cache_root=cache_root)
    if not study:
        return None
    status_raw = str(study.get("status") or "").upper().strip()
    if not status_raw:
        return None
    last_synced = _read_cached_at(_cache_path(cache_root, nct_id))
    return TrialStatusBadge(
        nct_id=nct_id,
        status=status_raw,
        is_recruiting=status_raw in _RECRUITING_STATUSES,
        last_synced=last_synced,
    )


def _read_cached_at(path: Path) -> Optional[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("cached_at")
    except (OSError, json.JSONDecodeError):
        return None


__all__ = [
    "DEFAULT_CACHE_ROOT",
    "TrialStatusBadge",
    "extract_nct_ids",
    "extract_nct_ids_from_files",
    "load_study_from_cache",
    "save_study_to_cache",
    "trial_status_badge",
]
