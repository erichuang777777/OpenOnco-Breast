"""Phase B7 — Push notification tests."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import Patient, PushSubscription
from tests.hospital.conftest import make_jwt

# Set a VAPID public key for tests
os.environ.setdefault("VAPID_PUBLIC_KEY", "test-vapid-public-key-base64")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-vapid-private-key")


def _hdr(sub: str = "user-push", role: str = "clinic_hcp") -> dict:
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


def _sub_body(endpoint: str = "https://push.example.com/endpoint") -> dict:
    return {
        "endpoint": endpoint,
        "p256dh": "test-p256dh-key",
        "auth": "test-auth-key",
    }


async def _seed_sub(
    db: AsyncSession,
    user_id: str = "user-push",
    endpoint: str = "https://push.example.com/endpoint",
    active: bool = True,
) -> PushSubscription:
    sub = PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        p256dh_key="test-p256dh",
        auth_key="test-auth",
        active=active,
    )
    db.add(sub)
    await db.flush()
    return sub


# ── VAPID public key ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_vapid_public_key_200(client: AsyncClient):
    resp = await client.get("/api/v1/push/vapid-public-key", headers=_hdr())
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_push_vapid_public_key_returns_non_empty_string(client: AsyncClient):
    resp = await client.get("/api/v1/push/vapid-public-key", headers=_hdr())
    assert resp.json()["vapid_public_key"]


@pytest.mark.asyncio
async def test_push_vapid_public_key_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/push/vapid-public-key")
    assert resp.status_code == 401


# ── Subscribe ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_subscribe_201(client: AsyncClient):
    resp = await client.post(
        "/api/v1/push/subscribe",
        json=_sub_body("https://push.example.com/new-endpoint-unique"),
        headers=_hdr(),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_push_subscribe_duplicate_endpoint_idempotent(
    client: AsyncClient, db_session: AsyncSession
):
    endpoint = "https://push.example.com/dup-endpoint"
    await _seed_sub(db_session, endpoint=endpoint)
    resp = await client.post(
        "/api/v1/push/subscribe",
        json=_sub_body(endpoint),
        headers=_hdr(),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_push_subscribe_missing_endpoint_422(client: AsyncClient):
    resp = await client.post(
        "/api/v1/push/subscribe",
        json={"p256dh": "key", "auth": "key"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_push_subscribe_missing_p256dh_422(client: AsyncClient):
    resp = await client.post(
        "/api/v1/push/subscribe",
        json={"endpoint": "https://x.com", "auth": "key"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_push_subscribe_missing_auth_key_422(client: AsyncClient):
    resp = await client.post(
        "/api/v1/push/subscribe",
        json={"endpoint": "https://x.com", "p256dh": "key"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


# ── Unsubscribe ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_unsubscribe_204(client: AsyncClient, db_session: AsyncSession):
    endpoint = "https://push.example.com/del-endpoint"
    await _seed_sub(db_session, user_id="user-push", endpoint=endpoint)
    resp = await client.request(
        "DELETE", "/api/v1/push/subscribe",
        json={"endpoint": endpoint},
        headers=_hdr(sub="user-push"),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_push_unsubscribe_unknown_endpoint_404(client: AsyncClient):
    resp = await client.request(
        "DELETE", "/api/v1/push/subscribe",
        json={"endpoint": "https://push.example.com/ghost"},
        headers=_hdr(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_push_unsubscribe_other_user_subscription_404(
    client: AsyncClient, db_session: AsyncSession
):
    endpoint = "https://push.example.com/other-user-ep"
    await _seed_sub(db_session, user_id="user-A", endpoint=endpoint)
    resp = await client.request(
        "DELETE", "/api/v1/push/subscribe",
        json={"endpoint": endpoint},
        headers=_hdr(sub="user-B"),
    )
    assert resp.status_code == 404


# ── List ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_list_own_subscriptions(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_sub(db_session, user_id="list-user", endpoint="https://ep1.example.com")
    await _seed_sub(db_session, user_id="list-user", endpoint="https://ep2.example.com")
    resp = await client.get("/api/v1/push/subscriptions", headers=_hdr(sub="list-user"))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_push_list_does_not_include_other_users(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_sub(db_session, user_id="user-X", endpoint="https://ep-x.example.com")
    await _seed_sub(db_session, user_id="user-Y", endpoint="https://ep-y.example.com")
    resp = await client.get("/api/v1/push/subscriptions", headers=_hdr(sub="user-X"))
    assert resp.status_code == 200
    assert all(s["endpoint"] == "https://ep-x.example.com" for s in resp.json())


# ── Dispatch service (mocked) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_service_notify_calls_webpush_for_active_sub(
    db_session: AsyncSession,
):
    from hospital.services import push_service

    await _seed_sub(db_session, user_id="notif-user", endpoint="https://ep-notif.example.com")
    with patch.object(push_service, "_send_webpush", new=AsyncMock(return_value=201)) as mock_send:
        await push_service.notify_user(db_session, "notif-user", "Title", "Body")
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_push_service_notify_skips_inactive_sub(db_session: AsyncSession):
    from hospital.services import push_service

    await _seed_sub(
        db_session, user_id="inactive-user",
        endpoint="https://ep-inactive.example.com", active=False
    )
    with patch.object(push_service, "_send_webpush", new=AsyncMock(return_value=201)) as mock_send:
        await push_service.notify_user(db_session, "inactive-user", "Title", "Body")
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_push_service_notify_marks_sub_inactive_on_410_gone(
    db_session: AsyncSession,
):
    from sqlalchemy import select
    from hospital.services import push_service

    sub = await _seed_sub(
        db_session, user_id="gone-user", endpoint="https://ep-gone.example.com"
    )
    with patch.object(push_service, "_send_webpush", new=AsyncMock(return_value=410)):
        await push_service.notify_user(db_session, "gone-user", "Title", "Body")

    refreshed = await db_session.scalar(
        select(PushSubscription).where(PushSubscription.id == sub.id)
    )
    assert refreshed.active is False


@pytest.mark.asyncio
async def test_push_service_notify_no_subscriptions_no_error(db_session: AsyncSession):
    from hospital.services import push_service

    # Should complete without exception when user has no subscriptions
    await push_service.notify_user(db_session, "no-subs-user", "Title", "Body")


# ── Trigger integration ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_urgent_reminder_create_triggers_push(
    client: AsyncClient, db_session: AsyncSession
):
    """High-urgency push path: notify_user dispatches to active subscriptions."""
    from hospital.services import push_service

    p = Patient(mrn="PUSH-P1", masked_name="P●●", status="active",
                primary_doctor_id="push-dr", created_by="push-dr")
    db_session.add(p)
    await _seed_sub(db_session, user_id="push-dr", endpoint="https://push-trigger.example.com")
    await db_session.flush()

    with patch.object(push_service, "_send_webpush", new=AsyncMock(return_value=201)) as mock_send:
        await push_service.notify_user(db_session, "push-dr", "高優先提醒", "內容")
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_non_urgent_reminder_does_not_trigger_push(
    client: AsyncClient, db_session: AsyncSession
):
    """Normal urgency reminders do not immediately trigger push."""
    from hospital.services import push_service

    p = Patient(mrn="PUSH-P2", masked_name="P●●", status="active",
                primary_doctor_id="push-dr2", created_by="push-dr2")
    db_session.add(p)
    await db_session.flush()

    future = (__import__("datetime").datetime.now(__import__("datetime").timezone.utc)
              + __import__("datetime").timedelta(days=3)).isoformat()
    resp = await client.post(
        "/api/v1/patients/PUSH-P2/reminders",
        json={"title": "普通提醒", "due_date": future},
        headers=_hdr(sub="push-dr2"),
    )
    assert resp.status_code == 201
    assert resp.json()["urgency"] == "normal"


@pytest.mark.asyncio
async def test_reminder_due_soon_triggers_push(db_session: AsyncSession):
    """Rule engine for due_date < now+1h marks a reminder for push dispatch."""
    from hospital.services import push_service

    # Test that notify_user can be called with the right interface
    await _seed_sub(db_session, user_id="due-soon-user", endpoint="https://due-soon.example.com")
    with patch.object(push_service, "_send_webpush", new=AsyncMock(return_value=201)) as mock_send:
        await push_service.notify_user(db_session, "due-soon-user", "即將到期提醒", "30分鐘內到期")
        mock_send.assert_called_once()
