"""Tests for the clinical sign-off review API."""

from __future__ import annotations

import pytest

from tests.hospital.conftest import make_jwt

pytestmark = pytest.mark.asyncio

ENTITY = "indication/IND-BREAST-HER2-POS-MET-1L-THP"


def _admin(sub: str, email: str):
    return {"Authorization": f"Bearer {make_jwt(role='kb_admin', sub=sub, email=email)}"}


async def test_unsigned_requires_view_role(client, hcp_headers):
    resp = await client.get("/api/v1/admin/kb/unsigned", headers=hcp_headers)
    assert resp.status_code == 403


async def test_list_unsigned(client, admin_headers):
    resp = await client.get("/api/v1/admin/kb/unsigned?entity_type=algorithm", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    assert all(e["entity_type"] == "algorithm" for e in body["entities"])
    assert all(e["signoff_count"] < 2 for e in body["entities"])


async def test_review_bundle(client, admin_headers):
    resp = await client.get(f"/api/v1/admin/kb/entity/{ENTITY}", headers=admin_headers)
    assert resp.status_code == 200
    b = resp.json()
    assert b["entity_id"] == "IND-BREAST-HER2-POS-MET-1L-THP"
    assert b["disease_id"] == "DIS-BREAST"
    assert any(c["field"] == "recommended_regimen" for c in b["claims"])
    assert b["citation_count"] >= 1
    assert any(c["found"] and c["url"] for c in b["citations"])
    assert "raw_yaml" in b and "recommended_regimen" in b["raw_yaml"]


async def test_review_bundle_unknown_404(client, admin_headers):
    resp = await client.get("/api/v1/admin/kb/entity/indication/IND-NOPE", headers=admin_headers)
    assert resp.status_code == 404


async def test_signoff_two_distinct_reviewers_approves(client):
    r1 = _admin("lead-1", "lead1@test.com")
    r2 = _admin("lead-2", "lead2@test.com")

    # First sign-off → still pending, awaiting second.
    a = await client.post(f"/api/v1/admin/kb/entity/{ENTITY}/signoff",
                          json={"decision": "approve", "comment": "verified vs CLEOPATRA"}, headers=r1)
    assert a.status_code == 200
    assert a.json()["status"] == "pending"
    assert a.json()["reviewer_1"] == "lead-1"

    # Same reviewer again → blocked.
    dup = await client.post(f"/api/v1/admin/kb/entity/{ENTITY}/signoff",
                            json={"decision": "approve"}, headers=r1)
    assert dup.status_code == 409

    # Second distinct reviewer → approved.
    b = await client.post(f"/api/v1/admin/kb/entity/{ENTITY}/signoff",
                          json={"decision": "approve"}, headers=r2)
    assert b.status_code == 200
    assert b.json()["status"] == "approved"
    assert b.json()["reviewer_2"] == "lead-2"


async def test_signoff_requires_admin(client):
    token = make_jwt(role="auditor", sub="aud-9", email="aud@test.com")
    resp = await client.post(
        f"/api/v1/admin/kb/entity/{ENTITY}/signoff",
        json={"decision": "approve"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
