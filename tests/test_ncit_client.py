"""NCIt client — offline scaffold tests.

No live api-evsrest.nci.nih.gov calls. Live calls are gated behind
`OPENONCO_NCIT_LIVE`; this suite leaves it unset and verifies refusal.
The HTTP seam is monkeypatched to return fixture payloads; cache and
rate-limit infrastructure from BaseSourceClient is exercised end-to-end
via `fetch()`.

Audit: docs/reviews/ncit-license-2026-05-18.md
Spec:  specs/SOURCE_INGESTION_SPEC.md §8, §20
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_base.clients import ncit_client
from knowledge_base.clients.base import InMemoryCacheBackend
from knowledge_base.clients.ncit_client import NcitClient, NcitQuery


_FIXTURES = Path(__file__).parent / "fixtures" / "ncit_responses"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


# ── Gate semantics ────────────────────────────────────────────────────────


def test_offline_mode_refuses_to_fetch(monkeypatch):
    monkeypatch.delenv("OPENONCO_NCIT_LIVE", raising=False)
    client = NcitClient(cache=InMemoryCacheBackend())
    with pytest.raises(RuntimeError, match="OPENONCO_NCIT_LIVE"):
        client.fetch(NcitQuery(mode="get_concept", code="C2926"))


def test_health_reports_offline_gate_when_env_unset(monkeypatch):
    monkeypatch.delenv("OPENONCO_NCIT_LIVE", raising=False)
    client = NcitClient(cache=InMemoryCacheBackend())
    out = client.health()
    assert out["ok"] is True
    assert "OPENONCO_NCIT_LIVE" in out["note"]


# ── Live-flag path with monkeypatched HTTP ────────────────────────────────


def test_get_concept_by_code_returns_fixture_via_cache(monkeypatch):
    monkeypatch.setenv("OPENONCO_NCIT_LIVE", "1")
    fixture = _load_fixture("concept_c2926_nsclc.json")

    captured_urls: list[str] = []

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured_urls.append(url)
        return fixture

    monkeypatch.setattr(ncit_client, "_http_get_json", fake_get)

    client = NcitClient(cache=InMemoryCacheBackend())
    resp1 = client.fetch(NcitQuery(mode="get_concept", code="C2926"))
    assert resp1.cache_hit is False
    assert resp1.source_id == "SRC-NCIT"
    assert resp1.data["code"] == "C2926"
    assert resp1.data["name"] == "Non-Small Cell Lung Carcinoma"

    resp2 = client.fetch(NcitQuery(mode="get_concept", code="C2926"))
    assert resp2.cache_hit is True
    assert len(captured_urls) == 1
    assert "C2926" in captured_urls[0]
    assert "include=summary" in captured_urls[0]


def test_search_passes_query_params(monkeypatch):
    monkeypatch.setenv("OPENONCO_NCIT_LIVE", "1")
    fixture = _load_fixture("search_egfr.json")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return fixture

    monkeypatch.setattr(ncit_client, "_http_get_json", fake_get)
    client = NcitClient(cache=InMemoryCacheBackend())
    resp = client.fetch(NcitQuery(mode="search", term="EGFR", max_results=10))
    assert resp.data["total"] == 23
    assert "term=EGFR" in captured["url"]
    assert "pageSize=10" in captured["url"]


def test_get_concept_requires_code(monkeypatch):
    monkeypatch.setenv("OPENONCO_NCIT_LIVE", "1")
    monkeypatch.setattr(ncit_client, "_http_get_json", lambda url, timeout=20: {})  # noqa: ARG005

    client = NcitClient(cache=InMemoryCacheBackend())
    with pytest.raises(ValueError, match="code"):
        client.fetch(NcitQuery(mode="get_concept", code=None))


def test_search_size_capped_at_100(monkeypatch):
    monkeypatch.setenv("OPENONCO_NCIT_LIVE", "1")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return {"concepts": []}

    monkeypatch.setattr(ncit_client, "_http_get_json", fake_get)

    client = NcitClient(cache=InMemoryCacheBackend())
    client.fetch(NcitQuery(mode="search", term="x", max_results=10_000))
    assert "pageSize=100" in captured["url"]


def test_url_encoding_of_code(monkeypatch):
    monkeypatch.setenv("OPENONCO_NCIT_LIVE", "1")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return {}

    monkeypatch.setattr(ncit_client, "_http_get_json", fake_get)
    client = NcitClient(cache=InMemoryCacheBackend())
    # NCIt codes are always C<digits> in practice, but be defensive about
    # reserved chars getting in via a malformed call.
    client.fetch(NcitQuery(mode="get_concept", code="C/12?34"))
    assert "C%2F12%3F34" in captured["url"]


def test_include_parameter_round_trips(monkeypatch):
    """`include=full` requests parents + children; default is `summary`."""
    monkeypatch.setenv("OPENONCO_NCIT_LIVE", "1")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return {}

    monkeypatch.setattr(ncit_client, "_http_get_json", fake_get)
    client = NcitClient(cache=InMemoryCacheBackend())
    client.fetch(NcitQuery(mode="get_concept", code="C2926", include="full"))
    assert "include=full" in captured["url"]


# ── Source entity ─────────────────────────────────────────────────────────


def test_source_entity_loads_and_carries_license_metadata():
    """src_ncit.yaml must parse cleanly under the Source schema and
    carry the public-domain / referenced-hosting classification."""
    import yaml
    from knowledge_base.schemas import Source

    path = (
        Path(__file__).parent.parent
        / "knowledge_base"
        / "hosted"
        / "content"
        / "sources"
        / "src_ncit.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    src = Source.model_validate(raw)
    assert src.id == "SRC-NCIT"
    assert src.hosting_mode.value == "referenced"
    assert src.commercial_use_allowed is True
    assert src.redistribution_allowed is True
    assert src.modifications_allowed is True
    assert src.sharealike_required is False
    assert src.license is not None
    assert "Public Domain" in src.license.name
    assert src.legal_review is not None
    assert src.legal_review.status.value == "reviewed"


def test_source_id_matches_client_constant():
    """Drift guard: a rename of either side without the other should
    surface here, not in production."""
    from knowledge_base.schemas import Source
    import yaml

    path = (
        Path(__file__).parent.parent
        / "knowledge_base"
        / "hosted"
        / "content"
        / "sources"
        / "src_ncit.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    src = Source.model_validate(raw)
    assert NcitClient.source_id == src.id


# ── Schema additions ──────────────────────────────────────────────────────


def test_disease_codes_accepts_ncit_field():
    """`DiseaseCodes.ncit` should round-trip — backs the normalization
    layer that maps free-text disease terms to KB IDs."""
    from knowledge_base.schemas.disease import DiseaseCodes

    codes = DiseaseCodes.model_validate({"icd_10": "C34.9", "ncit": "C2926"})
    assert codes.ncit == "C2926"
    assert codes.icd_10 == "C34.9"


def test_disease_codes_ncit_optional():
    """Existing Disease YAMLs predate this field. They must still load."""
    from knowledge_base.schemas.disease import DiseaseCodes

    codes = DiseaseCodes.model_validate({"icd_10": "C34.9"})
    assert codes.ncit is None


def test_biomarker_external_ids_accepts_ncit_field():
    from knowledge_base.schemas.biomarker import BiomarkerExternalIDs

    ids = BiomarkerExternalIDs.model_validate(
        {"hgnc_symbol": "EGFR", "ncit": "C20188"}
    )
    assert ids.ncit == "C20188"
    assert ids.hgnc_symbol == "EGFR"


def test_biomarker_external_ids_ncit_optional():
    from knowledge_base.schemas.biomarker import BiomarkerExternalIDs

    ids = BiomarkerExternalIDs.model_validate({"hgnc_symbol": "EGFR"})
    assert ids.ncit is None
