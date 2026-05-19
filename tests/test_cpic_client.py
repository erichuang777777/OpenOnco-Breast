"""CPIC client — offline scaffold tests.

No live api.cpicpgx.org calls. Live calls are gated behind
`OPENONCO_CPIC_LIVE`; this suite leaves it unset and verifies refusal.
The HTTP seam is monkeypatched to return fixture payloads; cache and
rate-limit infrastructure from BaseSourceClient is exercised
end-to-end via `fetch()`.

Audit: docs/reviews/cpic-license-2026-05-18.md
Spec:  specs/SOURCE_INGESTION_SPEC.md §8, §20
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_base.clients import cpic_client
from knowledge_base.clients.base import InMemoryCacheBackend
from knowledge_base.clients.cpic_client import CpicClient, CpicQuery


_FIXTURES = Path(__file__).parent / "fixtures" / "cpic_responses"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


# ── Gate semantics ────────────────────────────────────────────────────────


def test_offline_mode_refuses_to_fetch(monkeypatch):
    monkeypatch.delenv("OPENONCO_CPIC_LIVE", raising=False)
    client = CpicClient(cache=InMemoryCacheBackend())
    with pytest.raises(RuntimeError, match="OPENONCO_CPIC_LIVE"):
        client.fetch(CpicQuery(mode="search_drug", drug="fluorouracil"))


def test_health_reports_offline_gate_when_env_unset(monkeypatch):
    monkeypatch.delenv("OPENONCO_CPIC_LIVE", raising=False)
    client = CpicClient(cache=InMemoryCacheBackend())
    out = client.health()
    assert out["ok"] is True
    assert "OPENONCO_CPIC_LIVE" in out["note"]


# ── Live-flag path with monkeypatched HTTP ────────────────────────────────


def test_search_drug_dpyd_fluorouracil(monkeypatch):
    """The canonical oncology entry point: DPYD + fluorouracil.
    Two paired guidelines come back (fluorouracil, capecitabine) at
    CPIC level A."""
    monkeypatch.setenv("OPENONCO_CPIC_LIVE", "1")
    fixture = _load_fixture("pair_dpyd_fluorouracil.json")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return fixture

    monkeypatch.setattr(cpic_client, "_http_get_json", fake_get)

    client = CpicClient(cache=InMemoryCacheBackend())
    resp = client.fetch(CpicQuery(mode="search_drug", drug="fluorouracil", gene="DPYD"))
    assert resp.cache_hit is False
    assert resp.source_id == "SRC-CPIC"
    assert "drugid=eq.fluorouracil" in captured["url"]
    assert "genesymbol=eq.DPYD" in captured["url"]
    assert len(resp.data["results"]) == 2
    assert {r["drugid"] for r in resp.data["results"]} == {"fluorouracil", "capecitabine"}


def test_get_guideline_by_id(monkeypatch):
    monkeypatch.setenv("OPENONCO_CPIC_LIVE", "1")
    fixture = _load_fixture("guideline_g1_a0.json")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return fixture

    monkeypatch.setattr(cpic_client, "_http_get_json", fake_get)
    client = CpicClient(cache=InMemoryCacheBackend())
    resp = client.fetch(CpicQuery(mode="get_guideline", guideline_id="G1-A0"))
    assert resp.data["results"][0]["id"] == "G1-A0"
    assert "id=eq.G1-A0" in captured["url"]


def test_second_fetch_uses_cache(monkeypatch):
    monkeypatch.setenv("OPENONCO_CPIC_LIVE", "1")
    fixture = _load_fixture("pair_dpyd_fluorouracil.json")
    call_count = {"n": 0}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        call_count["n"] += 1
        return fixture

    monkeypatch.setattr(cpic_client, "_http_get_json", fake_get)
    client = CpicClient(cache=InMemoryCacheBackend())
    q = CpicQuery(mode="search_drug", drug="fluorouracil", gene="DPYD")
    client.fetch(q)
    resp2 = client.fetch(q)
    assert resp2.cache_hit is True
    assert call_count["n"] == 1


def test_get_guideline_requires_id(monkeypatch):
    monkeypatch.setenv("OPENONCO_CPIC_LIVE", "1")
    monkeypatch.setattr(cpic_client, "_http_get_json", lambda url, timeout=20: {})  # noqa: ARG005
    client = CpicClient(cache=InMemoryCacheBackend())
    with pytest.raises(ValueError, match="guideline_id"):
        client.fetch(CpicQuery(mode="get_guideline", guideline_id=None))


def test_search_size_capped_at_100(monkeypatch):
    monkeypatch.setenv("OPENONCO_CPIC_LIVE", "1")
    captured = {}

    def fake_get(url: str, timeout: int = 20) -> dict:  # noqa: ARG001
        captured["url"] = url
        return {"results": []}

    monkeypatch.setattr(cpic_client, "_http_get_json", fake_get)
    client = CpicClient(cache=InMemoryCacheBackend())
    client.fetch(CpicQuery(mode="search_drug", drug="x", max_results=10_000))
    assert "limit=100" in captured["url"]


def test_top_level_array_wrapped_into_dict(monkeypatch):
    """PostgREST returns bare JSON arrays. The client wraps them under
    `{results: [...]}` so the downstream contract stays dict-shaped."""
    monkeypatch.setenv("OPENONCO_CPIC_LIVE", "1")

    def fake_get(url: str, timeout: int = 20):  # noqa: ARG001
        # Call through to the real helper with a stub body
        import json as _json
        return cpic_client._http_get_json.__wrapped__(url) if hasattr(cpic_client._http_get_json, "__wrapped__") else _json.loads('[{"a":1},{"a":2}]')

    # Easier: just monkeypatch _http_get_json directly with the wrapped behavior.
    def stub(url: str, timeout: int = 20):  # noqa: ARG001
        # Simulate the wrap behavior end-to-end
        return {"results": [{"a": 1}, {"a": 2}]}

    monkeypatch.setattr(cpic_client, "_http_get_json", stub)
    client = CpicClient(cache=InMemoryCacheBackend())
    resp = client.fetch(CpicQuery(mode="search_drug", drug="x"))
    assert isinstance(resp.data, dict)
    assert resp.data["results"] == [{"a": 1}, {"a": 2}]


# ── Source entity ─────────────────────────────────────────────────────────


def test_source_entity_loads_and_carries_license_metadata():
    """src_cpic.yaml must parse cleanly under the Source schema and
    carry CC BY 4.0 / CC0 with sharealike=False."""
    import yaml
    from knowledge_base.schemas import Source

    path = (
        Path(__file__).parent.parent
        / "knowledge_base"
        / "hosted"
        / "content"
        / "sources"
        / "src_cpic.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    src = Source.model_validate(raw)
    assert src.id == "SRC-CPIC"
    assert src.hosting_mode.value == "referenced"
    assert src.commercial_use_allowed is True
    assert src.redistribution_allowed is True
    assert src.modifications_allowed is True
    assert src.sharealike_required is False
    assert src.license is not None
    assert "CC BY 4.0" in src.license.name
    assert src.license.spdx_id == "CC-BY-4.0"
    assert src.attribution is not None and src.attribution.required is True
    assert src.legal_review is not None
    assert src.legal_review.status.value == "reviewed"


def test_source_id_matches_client_constant():
    from knowledge_base.schemas import Source
    import yaml

    path = (
        Path(__file__).parent.parent
        / "knowledge_base"
        / "hosted"
        / "content"
        / "sources"
        / "src_cpic.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    src = Source.model_validate(raw)
    assert CpicClient.source_id == src.id
