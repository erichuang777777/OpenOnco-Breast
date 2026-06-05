"""Tests for /api/v1/admin/users endpoints."""

from __future__ import annotations

import pytest
from hospital.db.models import User


async def _seed_user(db_session, role="clinic_hcp", email="test@example.com", active=True):
    user = User(
        user_id=f"uid-{email}",
        google_sub=f"sub-{email}",
        google_email=email,
        google_name="Test User",
        role=role,
        active=active,
    )
    db_session.add(user)
    await db_session.flush()
    return user


class TestListUsers:
    @pytest.mark.asyncio
    async def test_admin_can_list(self, client, db_session, admin_headers):
        await _seed_user(db_session, role="clinic_hcp", email="hcp@test.com")
        resp = await client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, hcp_headers):
        resp = await client.get("/api/v1/admin/users", headers=hcp_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get("/api/v1/admin/users")
        assert resp.status_code == 401


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_admin_can_assign_role(self, client, db_session, admin_headers):
        user = await _seed_user(db_session, role="pending", email="pending@test.com")
        resp = await client.patch(
            f"/api/v1/admin/users/{user.user_id}",
            json={"role": "clinic_hcp"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "clinic_hcp"

    @pytest.mark.asyncio
    async def test_admin_can_deactivate(self, client, db_session, admin_headers):
        user = await _seed_user(db_session, role="clinic_hcp", email="deact@test.com")
        resp = await client.patch(
            f"/api/v1/admin/users/{user.user_id}",
            json={"active": False},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_404(self, client, admin_headers):
        resp = await client.patch(
            "/api/v1/admin/users/does-not-exist",
            json={"role": "clinic_hcp"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_assign_pending_role(self, client, db_session, admin_headers):
        user = await _seed_user(db_session, role="clinic_hcp", email="nopend@test.com")
        resp = await client.patch(
            f"/api/v1/admin/users/{user.user_id}",
            json={"role": "pending"},  # not in ASSIGNABLE_ROLES
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestDeactivateUser:
    @pytest.mark.asyncio
    async def test_delete_soft_deactivates(self, client, db_session, admin_headers):
        user = await _seed_user(db_session, role="clinic_hcp", email="softdel@test.com")
        resp = await client.delete(
            f"/api/v1/admin/users/{user.user_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_cannot_self_deactivate(self, client, db_session, admin_headers):
        # admin_headers uses sub="admin-001"
        admin = await _seed_user(db_session, role="kb_admin", email="admin@test.com")
        # Override admin headers to use the seeded user's ID
        from tests.hospital.conftest import make_jwt
        token = make_jwt(sub="admin-001", role="kb_admin")
        headers = {"Authorization": f"Bearer {token}"}
        # Seed a user with user_id="admin-001"
        self_user = User(
            user_id="admin-001",
            google_sub="sub-admin-001",
            google_email="admin@self.com",
            google_name="Self",
            role="kb_admin",
        )
        db_session.add(self_user)
        await db_session.flush()

        resp = await client.delete(
            "/api/v1/admin/users/admin-001",
            headers=headers,
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "SELF_DEACTIVATE"


class TestKbReviews:
    @pytest.mark.asyncio
    async def test_list_pending_reviews_empty(self, client, admin_headers):
        resp = await client.get("/api/v1/admin/kb/reviews", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["pending"] == []

    @pytest.mark.asyncio
    async def test_nonexistent_review_returns_404(self, client, admin_headers):
        resp = await client.patch(
            "/api/v1/admin/kb/reviews/no-such-review",
            json={"action": "approve"},
            headers=admin_headers,
        )
        assert resp.status_code == 404
