"""Tests for the claim-grounding audit (slice 3 of citation-verifier).

Covers:
  - Claim extraction shape: anchor presence/absence; structured outcomes
  - Real KB sanity (claim count > threshold; all expected entity types)
  - Semantic call mocked end-to-end through the audit
  - Cache hit + cache invalidation on content change
  - CLI smoke run against real KB
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from knowledge_base.engine._claim_extraction import (
    CLAIM_BEARING_ENTITIES,
    ExtractedClaim,
    extract_claims,
)
from knowledge_base.validation.loader import clear_load_cache, load_content
from scripts import audit_claim_grounding as aud


REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_KB = REPO_ROOT / "knowledge_base" / "hosted" / "content"


# ---------- helpers ----------

def _build_synthetic_kb(root: Path, *, with_anchor: bool) -> None:
    """Lay out a tiny KB so the loader produces a LoadResult.

    Always provides one Disease, one Drug, one Source, plus a Regimen
    (bare bones). The extra `with_anchor` flag toggles whether the
    Indication/BMA/Regimen reference SRC-* IDs.
    """
    (root / "diseases").mkdir(parents=True, exist_ok=True)
    (root / "drugs").mkdir(parents=True, exist_ok=True)
    (root / "regimens").mkdir(parents=True, exist_ok=True)
    (root / "indications").mkdir(parents=True, exist_ok=True)
    (root / "biomarkers").mkdir(parents=True, exist_ok=True)
    (root / "biomarker_actionability").mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir(parents=True, exist_ok=True)

    (root / "diseases" / "dis_test.yaml").write_text(
        yaml.safe_dump({
            "id": "DIS-TEST",
            "names": {"preferred": "Test cancer", "ukrainian": "Тест"},
            "codes": {"icd_10": "C00"},
        }),
        encoding="utf-8",
    )
    (root / "drugs" / "drug_test.yaml").write_text(
        yaml.safe_dump({
            "id": "DRUG-TEST",
            "names": {"preferred": "Testdrug"},
            "drug_class": "test",
        }),
        encoding="utf-8",
    )
    (root / "biomarkers" / "bio_test.yaml").write_text(
        yaml.safe_dump({
            "id": "BIO-TEST",
            "names": {"preferred": "Test biomarker"},
        }),
        encoding="utf-8",
    )
    (root / "sources" / "src_test.yaml").write_text(
        yaml.safe_dump({
            "id": "SRC-TEST",
            "source_type": "guideline",
            "title": "Test guideline",
            "evidence_tier": 1,
        }),
        encoding="utf-8",
    )

    reg_payload: dict = {
        "id": "REG-TEST",
        "name": "Test Regimen",
        "components": [{"drug_id": "DRUG-TEST"}],
        "notes": (
            "Median PFS ~7 months in OlympiAD per the cited NCCN guideline."
        ),
    }
    if with_anchor:
        reg_payload["sources"] = ["SRC-TEST"]
    (root / "regimens" / "reg_test.yaml").write_text(
        yaml.safe_dump(reg_payload), encoding="utf-8",
    )

    ind_payload: dict = {
        "id": "IND-TEST",
        "applicable_to": {
            "disease_id": "DIS-TEST",
            "line_of_therapy": 1,
        },
        "recommended_regimen": "REG-TEST",
        "rationale": "Test rationale: KEYNOTE-522 shows benefit.",
        "expected_outcomes": {
            "overall_response_rate": "~70%",
            "progression_free_survival": "median 7 months",
            "notes": "OlympiAD",
        },
    }
    if with_anchor:
        ind_payload["sources"] = [{"source_id": "SRC-TEST", "weight": "primary"}]
    (root / "indications" / "ind_test.yaml").write_text(
        yaml.safe_dump(ind_payload), encoding="utf-8",
    )

    bma_payload: dict = {
        "id": "BMA-TEST",
        "biomarker_id": "BIO-TEST",
        "disease_id": "DIS-TEST",
        "escat_tier": "IB",
        "evidence_summary": "Test biomarker drives sensitivity to testdrug.",
        "primary_sources": ["SRC-TEST"] if with_anchor else [],
        "last_verified": "2026-04-27",
    }
    (root / "biomarker_actionability" / "bma_test.yaml").write_text(
        yaml.safe_dump(bma_payload), encoding="utf-8",
    )


# ---------- 1+2: claim extraction unit tests ----------

def test_extract_claims_indication(tmp_path: Path) -> None:
    """Synthetic Indication with cited source → ExtractedClaim with has_anchor=True."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=True)
    clear_load_cache()
    lr = load_content(kb)
    claims = extract_claims(lr.entities_by_id)

    ind_claims = [c for c in claims if c.entity_id == "IND-TEST"]
    assert len(ind_claims) >= 2  # rationale + expected_outcomes at minimum
    fields = {c.field for c in ind_claims}
    assert "rationale" in fields
    assert "expected_outcomes" in fields
    for c in ind_claims:
        assert c.has_anchor is True
        assert "SRC-TEST" in c.cited_sources


def test_extract_claims_no_anchor(tmp_path: Path) -> None:
    """Synthetic entity without cited SRC-* → has_anchor=False."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=False)
    clear_load_cache()
    lr = load_content(kb)
    claims = extract_claims(lr.entities_by_id)

    ind_claims = [c for c in claims if c.entity_id == "IND-TEST"]
    assert ind_claims, "expected indication claims even without anchor"
    for c in ind_claims:
        assert c.has_anchor is False
        assert c.cited_sources == []


def test_expected_outcomes_stringified(tmp_path: Path) -> None:
    """Structured ExpectedOutcomes → stringified prose blob, not Python repr."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=True)
    clear_load_cache()
    lr = load_content(kb)
    claims = extract_claims(lr.entities_by_id)
    eo_claims = [c for c in claims
                 if c.entity_id == "IND-TEST" and c.field == "expected_outcomes"]
    assert len(eo_claims) == 1
    text = eo_claims[0].text
    assert "overall_response_rate" in text
    assert "~70%" in text
    assert "OlympiAD" in text


# ---------- 3: real-KB sanity ----------

def test_extract_claims_real_kb() -> None:
    """Real KB walks produce > 100 claims and cover all 3 entity types."""
    if not REAL_KB.is_dir():
        pytest.skip("real KB not present in this checkout")
    clear_load_cache()
    lr = load_content(REAL_KB)
    claims = extract_claims(lr.entities_by_id)
    assert len(claims) > 100
    types = {c.entity_type for c in claims}
    for expected in CLAIM_BEARING_ENTITIES:
        assert expected in types, f"missing {expected} in extracted claims"


# ---------- 4: semantic call mocked end-to-end ----------

def test_check_semantic_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit invokes injected semantic_fn; report mentions the canned outcome."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=True)

    # Canned CheckResult-like object: ungrounded with high confidence
    canned_detail = "grounded=False conf=0.92 — fabricated source title"

    class _CR:
        layer = "semantic"
        passed = False
        detail = canned_detail

    semantic_fn = MagicMock(return_value=_CR())

    md_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    metrics, claims, grounding = aud.run_audit(
        kb,
        enable_semantic=True,
        use_cache=False,
        semantic_fn=semantic_fn,
        source_titles={"SRC-TEST": "Test guideline title"},
    )
    aud.write_reports(
        metrics, claims, grounding,
        semantic_enabled=True,
        md_path=md_path, json_path=json_path,
    )

    # Audit ran the semantic check at least once (one per anchored claim)
    assert semantic_fn.call_count >= 1
    assert metrics.semantic_ungrounded >= 1
    md_text = md_path.read_text(encoding="utf-8")
    assert "Grounding-fail claims" in md_text
    assert "fabricated source title" in md_text

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["semantic_enabled"] is True
    assert payload["metrics"]["semantic"]["ungrounded"] >= 1


# ---------- 5+6: cache behaviour ----------

def test_cache_skip_unchanged_claims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-existing cache entry prevents the API from being re-called."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=True)

    # Redirect cache dir to a tmp location
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(aud, "CACHE_DIR", cache_dir)

    # Pre-populate cache for every claim that will be extracted
    clear_load_cache()
    lr = load_content(kb)
    from knowledge_base.engine._claim_extraction import extract_claims as _extract
    pre_claims = [c for c in _extract(lr.entities_by_id) if c.has_anchor]
    assert pre_claims, "synthetic anchored KB produced no claims"

    fixed_now = datetime.now(timezone.utc).isoformat()
    for c in pre_claims:
        h = aud._claim_hash(c.text, c.cited_sources)
        path = aud._cache_path(c.entity_id, c.field, h)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "cached_at": fixed_now,
            "entity_type": c.entity_type,
            "entity_id": c.entity_id,
            "field": c.field,
            "content_hash": h,
            "result": {
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "field": c.field,
                "grounded": True,
                "confidence": 0.95,
                "reasoning": "from cache",
                "raw_detail": "grounded=True conf=0.95 — from cache",
                "skipped": False,
                "skip_reason": "",
            },
        }), encoding="utf-8")

    semantic_fn = MagicMock()
    metrics, claims, grounding = aud.run_audit(
        kb,
        enable_semantic=True,
        use_cache=True,
        semantic_fn=semantic_fn,
        source_titles={"SRC-TEST": "Test"},
    )
    # API NEVER called because cache hit on every anchored claim
    assert semantic_fn.call_count == 0
    assert metrics.semantic_grounded >= 1
    assert all(g.reasoning == "from cache" for g in grounding if not g.skipped)


def test_cache_invalidates_on_content_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modify a claim text → cache key changes → API called fresh."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=True)

    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(aud, "CACHE_DIR", cache_dir)

    # 1st run with canned-true
    class _CR:
        layer = "semantic"
        passed = True
        detail = "grounded=True conf=0.85 — initial"

    semantic_fn = MagicMock(return_value=_CR())
    aud.run_audit(
        kb,
        enable_semantic=True,
        use_cache=True,
        semantic_fn=semantic_fn,
        source_titles={"SRC-TEST": "Test"},
    )
    first_count = semantic_fn.call_count
    assert first_count >= 1

    # 2nd run unchanged → all hits cached
    aud.run_audit(
        kb,
        enable_semantic=True,
        use_cache=True,
        semantic_fn=semantic_fn,
        source_titles={"SRC-TEST": "Test"},
    )
    assert semantic_fn.call_count == first_count, "expected pure cache hit"

    # 3rd run after content edit → cache miss, semantic_fn called again
    ind_path = kb / "indications" / "ind_test.yaml"
    data = yaml.safe_load(ind_path.read_text(encoding="utf-8"))
    data["rationale"] = "DIFFERENT rationale text triggering new hash."
    ind_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    aud.run_audit(
        kb,
        enable_semantic=True,
        use_cache=True,
        semantic_fn=semantic_fn,
        source_titles={"SRC-TEST": "Test"},
    )
    assert semantic_fn.call_count > first_count


def test_cache_ttl_expiry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stale (>30d) cache entries are ignored."""
    kb = tmp_path / "kb"
    _build_synthetic_kb(kb, with_anchor=True)

    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(aud, "CACHE_DIR", cache_dir)

    clear_load_cache()
    lr = load_content(kb)
    from knowledge_base.engine._claim_extraction import extract_claims as _extract
    pre_claims = [c for c in _extract(lr.entities_by_id) if c.has_anchor]
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    for c in pre_claims:
        h = aud._claim_hash(c.text, c.cited_sources)
        path = aud._cache_path(c.entity_id, c.field, h)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "cached_at": stale_ts,
            "result": {
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "field": c.field,
                "grounded": True,
                "confidence": 0.99,
                "reasoning": "old",
                "raw_detail": "grounded=True conf=0.99 — old",
                "skipped": False,
                "skip_reason": "",
            },
        }), encoding="utf-8")

    class _CR:
        layer = "semantic"
        passed = True
        detail = "grounded=True conf=0.7 — fresh"

    semantic_fn = MagicMock(return_value=_CR())
    aud.run_audit(
        kb,
        enable_semantic=True,
        use_cache=True,
        semantic_fn=semantic_fn,
        source_titles={"SRC-TEST": "Test"},
    )
    # All cache entries were stale → all required fresh API calls
    assert semantic_fn.call_count == len(pre_claims)


# ---------- 7: smoke ----------

def test_audit_script_smoke(tmp_path: Path) -> None:
    """`audit_claim_grounding --limit 3 --no-cache` against real KB exits 0."""
    if not REAL_KB.is_dir():
        pytest.skip("real KB not present in this checkout")

    md_target = tmp_path / "report.md"
    json_target = tmp_path / "report.json"

    # Direct in-process call: subprocess wouldn't see our overrides, and
    # we want to verify report files written somewhere we can clean up.
    # --out-md/--out-json are what keep this smoke run out of the real
    # docs/ report: a --limit 3 run produces a partial audit, and writing
    # it to the canonical paths left the committed report looking like a
    # full audit with a handful of claims in it.
    rc_code = aud.main([
        "--limit", "3", "--no-cache",
        "--out-md", str(md_target),
        "--out-json", str(json_target),
    ])
    assert rc_code == 0
    assert md_target.is_file()
    assert json_target.is_file()
    payload = json.loads(json_target.read_text(encoding="utf-8"))
    assert "metrics" in payload
    assert payload["metrics"]["total_claims"] >= 1


# ---------- additional coverage ----------

def test_main_unknown_kb_root(tmp_path: Path, capsys) -> None:
    rc = aud.main(["--kb-root", str(tmp_path / "does-not-exist")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not a directory" in err


def test_grounding_from_check_result_skip_paths() -> None:
    """Detail strings that signal skip → GroundingResult.skipped=True."""
    class _C:
        detail = "skipped (no API key)"

    class _Claim:
        entity_type = "indications"
        entity_id = "IND-X"
        field = "notes"

    g = aud._grounding_from_check_result(_Claim(), _C())
    assert g.skipped is True
    assert g.grounded is None
