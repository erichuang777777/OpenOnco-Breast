"""PDQ client — offline scaffold tests.

No live cancer.gov calls. Live calls are gated behind the
`OPENONCO_PDQ_LIVE` env var; this suite leaves that unset and verifies
the client refuses to fetch. The HTTP seam is exercised by
monkeypatching `_http_get_json` to return fixture payloads, and the
cache + rate-limit infrastructure from BaseSourceClient gets covered
end-to-end via `fetch()`.

Audit: docs/reviews/pdq-license-2026-05-18.md
Spec:  specs/SOURCE_INGESTION_SPEC.md §8, §20
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_base.clients import pdq_client
from knowledge_base.clients.base import InMemoryCacheBackend
from knowledge_base.clients.pdq_client import PdqClient, PdqQuery


_FIXTURES = Path(__file__).parent / "fixtures" / "pdq_responses"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


# ── Gate semantics ────────────────────────────────────────────────────────


def test_offline_mode_refuses_to_fetch(monkeypatch):
    """Without OPENONCO_PDQ_LIVE set, _fetch_raw raises so a stray test
    can't accidentally hit cancer.gov."""
    monkeypatch.delenv("OPENONCO_PDQ_LIVE", raising=False)
    client = PdqClient(cache=InMemoryCacheBackend())
    with pytest.raises(RuntimeError, match="OPENONCO_PDQ_LIVE"):
        client.fetch(PdqQuery(mode="get_summary", cdr_id="CDR0000062955"))


def test_health_reports_offline_gate_when_env_unset(monkeypatch):
    monkeypatch.delenv("OPENONCO_PDQ_LIVE", raising=False)
    client = PdqClient(cache=InMemoryCacheBackend())
    out = client.health()
    assert out["ok"] is True
    assert "OPENONCO_PDQ_LIVE" in out["note"]


# ── Live-flag path with monkeypatched HTTP ────────────────────────────────


def test_get_summary_returns_fixture_via_cache(monkeypatch):
    """With the live flag set AND the HTTP seam stubbed, fetch() resolves
    the summary fixture and the result is cached on second call."""
    monkeypatch.setenv("OPENONCO_PDQ_LIVE", "1")
    fixture = _load_fixture("summary_breast_treatment_hp.json")

    captured_urls: list[str] = []

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured_urls.append(url)
        return fixture

    monkeypatch.setattr(pdq_client, "_http_get_json", fake_get)

    client = PdqClient(cache=InMemoryCacheBackend())
    resp1 = client.fetch(PdqQuery(mode="get_summary", cdr_id="CDR0000062955"))
    assert resp1.cache_hit is False
    assert resp1.source_id == "SRC-PDQ"
    assert resp1.api_version == "syndication-v1"
    assert resp1.data["cdr_id"] == "CDR0000062955"

    resp2 = client.fetch(PdqQuery(mode="get_summary", cdr_id="CDR0000062955"))
    assert resp2.cache_hit is True  # served from cache, no second HTTP call
    assert len(captured_urls) == 1
    assert "CDR0000062955" in captured_urls[0]
    assert captured_urls[0].startswith("https://www.cancer.gov/syndication")


def test_search_passes_query_params(monkeypatch):
    monkeypatch.setenv("OPENONCO_PDQ_LIVE", "1")
    fixture = _load_fixture("search_pembrolizumab.json")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return fixture

    monkeypatch.setattr(pdq_client, "_http_get_json", fake_get)
    client = PdqClient(cache=InMemoryCacheBackend())
    resp = client.fetch(
        PdqQuery(mode="search", terms="pembrolizumab", audience="hp", max_results=5)
    )
    assert resp.data["total"] == 7
    assert "terms=pembrolizumab" in captured["url"]
    assert "audience=hp" in captured["url"]
    assert "size=5" in captured["url"]


def test_get_summary_requires_cdr_id(monkeypatch):
    monkeypatch.setenv("OPENONCO_PDQ_LIVE", "1")
    monkeypatch.setattr(pdq_client, "_http_get_json", lambda url, timeout=20: {})  # noqa: ARG005

    client = PdqClient(cache=InMemoryCacheBackend())
    with pytest.raises(ValueError, match="cdr_id"):
        client.fetch(PdqQuery(mode="get_summary", cdr_id=None))


def test_search_size_capped_at_50(monkeypatch):
    """Tighter than NCI's plausible page-size; defensive against accidental
    over-fetch when a caller passes max_results=10_000."""
    monkeypatch.setenv("OPENONCO_PDQ_LIVE", "1")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return {"results": []}

    monkeypatch.setattr(pdq_client, "_http_get_json", fake_get)

    client = PdqClient(cache=InMemoryCacheBackend())
    client.fetch(PdqQuery(mode="search", terms="x", max_results=10_000))
    assert "size=50" in captured["url"]


def test_url_encoding_of_cdr_id(monkeypatch):
    """Defensive: if a caller passes a CDR ID containing reserved chars,
    we still produce a valid URL."""
    monkeypatch.setenv("OPENONCO_PDQ_LIVE", "1")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return {}

    monkeypatch.setattr(pdq_client, "_http_get_json", fake_get)
    client = PdqClient(cache=InMemoryCacheBackend())
    client.fetch(PdqQuery(mode="get_summary", cdr_id="CDR/00012?345"))
    assert "CDR%2F00012%3F345" in captured["url"]


# ── Source entity ─────────────────────────────────────────────────────────


def test_source_entity_loads_and_carries_license_metadata():
    """src_pdq.yaml must parse cleanly under the Source schema and carry
    the public-domain / referenced-hosting / no-attribution-required
    classification."""
    import yaml
    from knowledge_base.schemas import Source

    path = (
        Path(__file__).parent.parent
        / "knowledge_base"
        / "hosted"
        / "content"
        / "sources"
        / "src_pdq.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    src = Source.model_validate(raw)
    assert src.id == "SRC-PDQ"
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
        / "src_pdq.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    src = Source.model_validate(raw)
    assert PdqClient.source_id == src.id
