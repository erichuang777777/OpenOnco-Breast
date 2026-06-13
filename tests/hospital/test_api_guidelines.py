"""Tests for the guideline-flowchart visualization API."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_guidelines_requires_auth(client):
    resp = await client.get("/api/v1/guidelines")
    assert resp.status_code == 401


async def test_list_guidelines_filtered_by_disease(client, hcp_headers):
    resp = await client.get("/api/v1/guidelines?disease=DIS-BREAST", headers=hcp_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "algorithms" in body
    ids = [a["algorithm_id"] for a in body["algorithms"]]
    assert "ALGO-BREAST-1L" in ids
    # every returned algorithm is anchored to the requested disease
    assert all(a["disease_id"] == "DIS-BREAST" for a in body["algorithms"])


async def test_get_guideline_graph(client, hcp_headers):
    resp = await client.get("/api/v1/guidelines/ALGO-BREAST-1L", headers=hcp_headers)
    assert resp.status_code == 200
    graph = resp.json()
    assert graph["algorithm_id"] == "ALGO-BREAST-1L"
    assert graph["disease_id"] == "DIS-BREAST"

    kinds = {n["kind"] for n in graph["nodes"]}
    assert "start" in kinds
    assert "decision" in kinds
    assert "indication" in kinds

    # decision nodes carry human-readable conditions
    decisions = [n for n in graph["nodes"] if n["kind"] == "decision"]
    assert decisions
    assert any(n["conditions"] for n in decisions)

    # at least one indication terminal resolved a regimen name
    indications = [n for n in graph["nodes"] if n["kind"] == "indication"]
    assert indications
    assert any(n.get("regimen_name") for n in indications)

    # graph is connected from the start node
    assert any(e["source"] == "start" for e in graph["edges"])
    # no trace overlaid on a bare graph fetch
    assert graph["has_trace"] is False
    assert all(n["on_path"] is False for n in graph["nodes"])


async def test_get_guideline_graph_unknown_returns_404(client, hcp_headers):
    resp = await client.get("/api/v1/guidelines/ALGO-DOES-NOT-EXIST", headers=hcp_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "ALGORITHM_NOT_FOUND"


async def test_auditor_can_view_guidelines(client, admin_headers):
    # kb_admin (admin_headers) is a guideline viewer for the audit UI
    resp = await client.get("/api/v1/guidelines/ALGO-BREAST-1L", headers=admin_headers)
    assert resp.status_code == 200
