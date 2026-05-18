"""Tests for citation_enrichment — NCT extraction + cache I/O + badge build.

Closes the data side of Gap 3 from
`docs/reviews/ctgov-wiring-audit-2026-05-18.md`. Render-layer wiring is
a separate follow-up; this suite covers the foundation:

1. NCT extraction across nested dict / list / string payloads.
2. Cache round-trip (save → load), TTL expiry, error tolerance.
3. `TrialStatusBadge` build with the recruiting-status enum mapping.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from knowledge_base.engine.citation_enrichment import (
    TrialStatusBadge,
    extract_nct_ids,
    extract_nct_ids_from_files,
    load_study_from_cache,
    save_study_to_cache,
    trial_status_badge,
)


# ── NCT extraction ───────────────────────────────────────────────────────


def test_extract_nct_ids_from_flat_string_field():
    payload = {
        "notes": "ADAURA phase-3 (NCT02511106): adjuvant osimertinib 80 mg",
    }
    assert extract_nct_ids(payload) == ["NCT02511106"]


def test_extract_nct_ids_dedups_preserving_order():
    payload = {
        "summary": "NCT02220894 vs NCT02220894 (same trial, both arms)",
        "see_also": ["NCT04001023", "NCT02220894"],
    }
    out = extract_nct_ids(payload)
    assert out == ["NCT02220894", "NCT04001023"]


def test_extract_nct_ids_from_nested_structures():
    payload = {
        "trials": [
            {"citation": "Reck 2016 NEJM (NCT02220894)"},
            {"citation": "Mok 2017 (NCT02151981)"},
        ],
        "notes": "Confirmed by FLAURA NCT02296125 follow-up.",
    }
    out = extract_nct_ids(payload)
    assert out == ["NCT02220894", "NCT02151981", "NCT02296125"]


def test_extract_nct_ids_ignores_malformed_tokens():
    """ID must be exactly NCT + 8 digits. Anything shorter or longer doesn't match."""
    payload = {
        "notes": "Old format NCT123, future format NCT123456789, ok NCT12345678.",
    }
    assert extract_nct_ids(payload) == ["NCT12345678"]


def test_extract_nct_ids_empty_payload():
    assert extract_nct_ids(None) == []
    assert extract_nct_ids({}) == []
    assert extract_nct_ids([]) == []
    assert extract_nct_ids("") == []


def test_extract_nct_ids_string_payload_works():
    """Direct string input — not wrapped in dict."""
    assert extract_nct_ids("see NCT02220894 for details") == ["NCT02220894"]


# ── Multi-file extraction ────────────────────────────────────────────────


def test_extract_nct_ids_from_files(tmp_path: Path):
    f1 = tmp_path / "src_a.yaml"
    f1.write_text("notes: trial NCT02220894 was pivotal\n", encoding="utf-8")
    f2 = tmp_path / "src_b.yaml"
    f2.write_text(
        "notes: |\n  NCT02220894 again here\n  NCT02151981 also referenced\n",
        encoding="utf-8",
    )
    out = extract_nct_ids_from_files([f1, f2])
    assert "NCT02220894" in out
    assert "NCT02151981" in out
    assert sorted(out["NCT02220894"]) == ["src_a.yaml", "src_b.yaml"]
    assert out["NCT02151981"] == ["src_b.yaml"]


def test_extract_nct_ids_from_files_tolerates_malformed_yaml(tmp_path: Path):
    """A broken YAML should not crash the walk; just be skipped."""
    good = tmp_path / "ok.yaml"
    good.write_text("notes: NCT02220894\n", encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(":\n  - this is: : not: valid", encoding="utf-8")
    out = extract_nct_ids_from_files([good, bad])
    assert out["NCT02220894"] == ["ok.yaml"]


# ── Cache I/O ────────────────────────────────────────────────────────────


def test_save_and_load_round_trip(tmp_path: Path):
    study = {
        "nct_id": "NCT02220894",
        "title": "KEYNOTE-024",
        "status": "COMPLETED",
        "phase": "PHASE3",
    }
    save_study_to_cache("NCT02220894", study, cache_root=tmp_path)
    loaded = load_study_from_cache("NCT02220894", cache_root=tmp_path)
    assert loaded == study


def test_load_returns_none_when_missing(tmp_path: Path):
    assert load_study_from_cache("NCT99999999", cache_root=tmp_path) is None


def test_load_returns_none_on_corrupt_json(tmp_path: Path):
    path = tmp_path / "NCT02220894.json"
    path.write_text("{ this is not json", encoding="utf-8")
    assert load_study_from_cache("NCT02220894", cache_root=tmp_path) is None


def test_load_returns_none_past_max_age(tmp_path: Path):
    """A cache entry written 60 days ago must be rejected when
    max_age_days=30."""
    stale_payload = {
        "cached_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        "study": {"nct_id": "NCT02220894", "status": "COMPLETED"},
    }
    path = tmp_path / "NCT02220894.json"
    path.write_text(json.dumps(stale_payload), encoding="utf-8")
    assert load_study_from_cache("NCT02220894", cache_root=tmp_path, max_age_days=30) is None
    # Without max_age_days, it loads:
    assert load_study_from_cache("NCT02220894", cache_root=tmp_path) is not None


def test_save_creates_parent_directory(tmp_path: Path):
    """Cache root may not exist on first sync. save_study_to_cache must
    mkdir parents."""
    nested = tmp_path / "deeply" / "nested" / "cache"
    save_study_to_cache("NCT02220894", {"status": "COMPLETED"}, cache_root=nested)
    assert (nested / "NCT02220894.json").is_file()


# ── Badge build ──────────────────────────────────────────────────────────


def test_badge_for_recruiting_trial(tmp_path: Path):
    save_study_to_cache(
        "NCT04001023",
        {"nct_id": "NCT04001023", "status": "RECRUITING", "phase": "PHASE3"},
        cache_root=tmp_path,
    )
    badge = trial_status_badge("NCT04001023", cache_root=tmp_path)
    assert badge is not None
    assert badge.nct_id == "NCT04001023"
    assert badge.status == "RECRUITING"
    assert badge.is_recruiting is True
    assert badge.last_synced is not None


def test_badge_for_completed_trial(tmp_path: Path):
    save_study_to_cache(
        "NCT02220894",
        {"status": "COMPLETED"},
        cache_root=tmp_path,
    )
    badge = trial_status_badge("NCT02220894", cache_root=tmp_path)
    assert badge is not None
    assert badge.status == "COMPLETED"
    assert badge.is_recruiting is False


def test_badge_returns_none_when_not_cached(tmp_path: Path):
    assert trial_status_badge("NCT99999999", cache_root=tmp_path) is None


def test_badge_returns_none_when_status_missing(tmp_path: Path):
    """If the cached study has no status field (corrupt or partial
    fetch), don't fabricate a badge — return None."""
    save_study_to_cache("NCT04001023", {"nct_id": "NCT04001023"}, cache_root=tmp_path)
    assert trial_status_badge("NCT04001023", cache_root=tmp_path) is None


def test_recruiting_status_enum_covers_canonical_states(tmp_path: Path):
    """Drift guard: if NLM adds a new "open" status (e.g.
    SCREENING_NEW_PATIENTS), we want to know to update
    `_RECRUITING_STATUSES`. For now, document the expected mapping."""
    for s in ("RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"):
        save_study_to_cache("NCT04001023", {"status": s}, cache_root=tmp_path)
        b = trial_status_badge("NCT04001023", cache_root=tmp_path)
        assert b is not None and b.is_recruiting is True, f"{s} should map to is_recruiting=True"
    for s in ("COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED"):
        save_study_to_cache("NCT04001023", {"status": s}, cache_root=tmp_path)
        b = trial_status_badge("NCT04001023", cache_root=tmp_path)
        assert b is not None and b.is_recruiting is False, f"{s} should map to is_recruiting=False"


# ── Integration: real KB walks ───────────────────────────────────────────


def test_real_kb_extraction_finds_known_pivotal_ncts():
    """Smoke test against the real KB. The audit found 147 NCT IDs in
    Source files and 46 in Indication files — this asserts the walker
    surfaces well-known examples."""
    repo_root = Path(__file__).parent.parent
    sources = sorted((repo_root / "knowledge_base" / "hosted" / "content" / "sources").glob("*.yaml"))
    out = extract_nct_ids_from_files(sources)
    # Known well-cited pivotal trials (per audit). These are stable
    # references — if they disappear from the KB, that's signal worth
    # investigating, not a test bug.
    for nct in ("NCT02220894", "NCT02511106"):  # KEYNOTE-024, ADAURA
        assert nct in out, f"expected pivotal trial {nct} cited in Sources"
