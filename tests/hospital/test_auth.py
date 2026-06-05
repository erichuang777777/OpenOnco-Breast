"""Tests for JWT utilities and auth dependency enforcement."""

from __future__ import annotations

import pytest
from jose import JWTError


class TestJwtUtils:
    def test_create_and_decode(self):
        from hospital.auth.jwt_utils import create_access_token, decode_token
        token = create_access_token("sub-1", "a@b.com", "Alice", "clinic_hcp")
        payload = decode_token(token)
        assert payload["sub"] == "sub-1"
        assert payload["email"] == "a@b.com"
        assert payload["role"] == "clinic_hcp"

    def test_expired_token_raises(self):
        from hospital.auth.jwt_utils import create_access_token, decode_token
        token = create_access_token("s", "e", "n", "clinic_hcp", expire_minutes=-1)
        with pytest.raises(JWTError):
            decode_token(token)

    def test_tampered_token_raises(self):
        from hospital.auth.jwt_utils import create_access_token, decode_token
        token = create_access_token("s", "e", "n", "clinic_hcp")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(JWTError):
            decode_token(tampered)


class TestAuthMiddleware:
    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, client):
        resp = await client.post("/api/v1/plan", json={})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client):
        resp = await client.post(
            "/api/v1/plan", json={},
            headers={"Authorization": "Bearer not.a.real.token"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_pending_role_returns_403(self, client, pending_headers):
        resp = await client.post(
            "/api/v1/plan",
            json={"patient": {"disease": {"id": "DIS-BREAST"}}},
            headers=pending_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "ACCOUNT_PENDING"

    @pytest.mark.asyncio
    async def test_wrong_role_returns_403(self, client):
        from tests.hospital.conftest import make_jwt
        token = make_jwt(role="auditor")
        resp = await client.post(
            "/api/v1/plan",
            json={"patient": {"disease": {"id": "DIS-BREAST"}}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_health_requires_no_auth(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200


class TestRequireRole:
    def test_hcp_allowed_on_hcp_endpoint(self):
        from hospital.auth.dependencies import HCP_ROLES
        assert "clinic_hcp" in HCP_ROLES
        assert "tumor_board_hcp" in HCP_ROLES

    def test_patient_not_in_hcp_roles(self):
        from hospital.auth.dependencies import HCP_ROLES
        assert "patient" not in HCP_ROLES
