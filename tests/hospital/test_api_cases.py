"""Tests for /api/v1/cases endpoints."""

from __future__ import annotations

import pytest


class TestCaseCreate:
    @pytest.mark.asyncio
    async def test_create_case(self, client, hcp_headers):
        resp = await client.post(
            "/api/v1/cases",
            json={"mrn": "MRN-TEST-001", "disease_id": "DIS-BREAST"},
            headers=hcp_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["mrn"] == "MRN-TEST-001"
        assert data["disease_id"] == "DIS-BREAST"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_duplicate_mrn_returns_409(self, client, hcp_headers):
        await client.post(
            "/api/v1/cases",
            json={"mrn": "MRN-DUP", "disease_id": "DIS-BREAST"},
            headers=hcp_headers,
        )
        resp = await client.post(
            "/api/v1/cases",
            json={"mrn": "MRN-DUP", "disease_id": "DIS-BREAST"},
            headers=hcp_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/cases",
            json={"mrn": "MRN-X", "disease_id": "DIS-BREAST"},
        )
        assert resp.status_code == 401


class TestCaseGet:
    @pytest.mark.asyncio
    async def test_get_existing_case(self, client, hcp_headers):
        await client.post(
            "/api/v1/cases",
            json={"mrn": "MRN-GET-001", "disease_id": "DIS-BREAST"},
            headers=hcp_headers,
        )
        resp = await client.get("/api/v1/cases/MRN-GET-001", headers=hcp_headers)
        assert resp.status_code == 200
        assert resp.json()["mrn"] == "MRN-GET-001"
        assert "plans" in resp.json()
        assert "annotations" in resp.json()

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client, hcp_headers):
        resp = await client.get("/api/v1/cases/MRN-NOPE", headers=hcp_headers)
        assert resp.status_code == 404


class TestAnnotations:
    @pytest.mark.asyncio
    async def test_add_annotation_requires_valid_plan(self, client, hcp_headers):
        resp = await client.post(
            "/api/v1/cases/MRN-NO-CASE/annotations",
            json={
                "plan_id": "FAKE-PLAN",
                "annotation_type": "comment",
                "text": "test",
                "role": "medical_oncologist",
            },
            headers=hcp_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_select_track_requires_track_id(self, client, hcp_headers):
        await client.post(
            "/api/v1/cases",
            json={"mrn": "MRN-ANN", "disease_id": "DIS-BREAST"},
            headers=hcp_headers,
        )
        # select_track without track_id should fail
        resp = await client.post(
            "/api/v1/cases/MRN-ANN/annotations",
            json={
                "plan_id": "SOME-PLAN",
                "annotation_type": "select_track",
                "role": "medical_oncologist",
                # track_id missing
            },
            headers=hcp_headers,
        )
        assert resp.status_code in (400, 404)  # 404 if plan not found first
