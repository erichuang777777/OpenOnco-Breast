"""Tests for the KB ingestion/verification status endpoint (audit interface)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_ingestion_status_requires_admin(client, hcp_headers):
    resp = await client.get("/api/v1/admin/kb/ingestion-status", headers=hcp_headers)
    assert resp.status_code == 403


async def test_ingestion_status_shape(client, admin_headers):
    resp = await client.get("/api/v1/admin/kb/ingestion-status", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_entities"] > 0
    assert body["content_counts"]["algorithms"] > 0
    assert body["content_counts"]["indications"] > 0
    assert body["content_counts"]["sources"] > 0

    assert "civic" in body and "snapshots" in body["civic"]
    assert "source_freshness" in body
    fresh = body["source_freshness"]
    assert fresh["total"] >= fresh["stale"]
    assert isinstance(fresh["stalest"], list)

    assert body["review_queue"]["pending"] == 0  # empty DB in test


async def test_ingestion_status_auditor_allowed(client):
    from tests.hospital.conftest import make_jwt
    token = make_jwt(role="auditor", sub="aud-1", email="aud@test.com")
    resp = await client.get(
        "/api/v1/admin/kb/ingestion-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
