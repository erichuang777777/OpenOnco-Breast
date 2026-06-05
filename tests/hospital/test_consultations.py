"""Phase B5 — Consultations tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import Consultation, Patient, User
from tests.hospital.conftest import make_jwt


def _hdr(role: str = "clinic_hcp", sub: str = "dr-a") -> dict:
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


async def _seed_patient(db: AsyncSession, mrn: str = "CON-P1") -> Patient:
    p = Patient(mrn=mrn, masked_name="C●●", status="active",
                primary_doctor_id="dr-a", created_by="dr-a")
    db.add(p)
    await db.flush()
    return p


async def _seed_user(db: AsyncSession, user_id: str, role: str = "clinic_hcp") -> User:
    u = User(
        user_id=user_id,
        google_sub=user_id,
        google_email=f"{user_id}@test.com",
        google_name=user_id,
        role=role,
        active=True,
    )
    db.add(u)
    await db.flush()
    return u


async def _seed_consultation(
    db: AsyncSession,
    mrn: str,
    from_id: str = "dr-a",
    to_id: str = "dr-b",
    subject: str = "請諮詢",
    status: str = "open",
) -> Consultation:
    c = Consultation(
        patient_mrn=mrn,
        from_user_id=from_id,
        to_user_id=to_id,
        subject=subject,
        status=status,
    )
    db.add(c)
    await db.flush()
    return c


# ── Create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consultation_create_201(client: AsyncClient, db_session: AsyncSession):
    await _seed_patient(db_session, "CRE-1")
    await _seed_user(db_session, "dr-b")
    resp = await client.post(
        "/api/v1/patients/CRE-1/consultations",
        json={"to_user_id": "dr-b", "subject": "HER2 治療建議"},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["patient_mrn"] == "CRE-1"
    assert data["status"] == "open"


@pytest.mark.asyncio
async def test_consultation_create_from_is_caller(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CRE-2")
    await _seed_user(db_session, "dr-b")
    resp = await client.post(
        "/api/v1/patients/CRE-2/consultations",
        json={"to_user_id": "dr-b", "subject": "subject"},
        headers=_hdr(sub="dr-a"),
    )
    assert resp.status_code == 201
    assert resp.json()["from_user_id"] == "dr-a"


@pytest.mark.asyncio
async def test_consultation_create_unknown_to_user_404(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CRE-3")
    resp = await client.post(
        "/api/v1/patients/CRE-3/consultations",
        json={"to_user_id": "nonexistent-user", "subject": "subject"},
        headers=_hdr(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_consultation_create_unknown_mrn_404(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_user(db_session, "dr-b")
    resp = await client.post(
        "/api/v1/patients/GHOST-MRN/consultations",
        json={"to_user_id": "dr-b", "subject": "subject"},
        headers=_hdr(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_consultation_create_pending_role_403(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CRE-4")
    await _seed_user(db_session, "dr-b")
    resp = await client.post(
        "/api/v1/patients/CRE-4/consultations",
        json={"to_user_id": "dr-b", "subject": "subject"},
        headers=_hdr(role="pending"),
    )
    assert resp.status_code == 403


# ── List per patient ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consultation_list_per_patient_returns_all(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LST-1")
    await _seed_consultation(db_session, "LST-1", subject="Q1")
    await _seed_consultation(db_session, "LST-1", subject="Q2")
    resp = await client.get("/api/v1/patients/LST-1/consultations", headers=_hdr())
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_consultation_list_per_patient_unknown_mrn_404(
    client: AsyncClient,
):
    resp = await client.get("/api/v1/patients/GHOST/consultations", headers=_hdr())
    assert resp.status_code == 404


# ── My consultations ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_my_consultations_received_returns_inbound(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "MY-1")
    await _seed_consultation(db_session, "MY-1", from_id="dr-a", to_id="dr-b")
    resp = await client.get(
        "/api/v1/consultations?role=received",
        headers=_hdr(sub="dr-b"),
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert all(c["to_user_id"] == "dr-b" for c in resp.json())


@pytest.mark.asyncio
async def test_my_consultations_sent_returns_outbound(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "MY-2")
    await _seed_consultation(db_session, "MY-2", from_id="dr-a", to_id="dr-b")
    resp = await client.get(
        "/api/v1/consultations?role=sent",
        headers=_hdr(sub="dr-a"),
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert all(c["from_user_id"] == "dr-a" for c in resp.json())


@pytest.mark.asyncio
async def test_my_consultations_all_returns_both(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "MY-3")
    # dr-c sent one, received one
    await _seed_consultation(db_session, "MY-3", from_id="dr-c", to_id="dr-d")
    await _seed_consultation(db_session, "MY-3", from_id="dr-d", to_id="dr-c")
    resp = await client.get(
        "/api/v1/consultations?role=all",
        headers=_hdr(sub="dr-c"),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Reply message ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consultation_reply_creates_message(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "REP-1")
    c = await _seed_consultation(db_session, "REP-1", from_id="dr-a", to_id="dr-b")
    resp = await client.post(
        f"/api/v1/consultations/{c.id}/messages",
        json={"body": "我的意見是繼續 THP"},
        headers=_hdr(sub="dr-b"),
    )
    assert resp.status_code == 201
    assert len(resp.json()["messages"]) == 1
    assert resp.json()["messages"][0]["body"] == "我的意見是繼續 THP"


@pytest.mark.asyncio
async def test_consultation_reply_updates_status_to_replied(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "REP-2")
    c = await _seed_consultation(db_session, "REP-2", from_id="dr-a", to_id="dr-b")
    resp = await client.post(
        f"/api/v1/consultations/{c.id}/messages",
        json={"body": "回覆"},
        headers=_hdr(sub="dr-b"),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "replied"


@pytest.mark.asyncio
async def test_consultation_reply_creates_timeline_event(
    client: AsyncClient, db_session: AsyncSession
):
    from sqlalchemy import select as sa_select
    from hospital.db.models import TimelineEvent

    await _seed_patient(db_session, "REP-3")
    c = await _seed_consultation(db_session, "REP-3", from_id="dr-a", to_id="dr-b")
    await client.post(
        f"/api/v1/consultations/{c.id}/messages",
        json={"body": "timeline test"},
        headers=_hdr(sub="dr-b"),
    )
    row = await db_session.scalar(
        sa_select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "REP-3",
            TimelineEvent.event_type == "consultation_reply",
        )
    )
    assert row is not None


@pytest.mark.asyncio
async def test_consultation_reply_by_third_party_403(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "REP-4")
    c = await _seed_consultation(db_session, "REP-4", from_id="dr-a", to_id="dr-b")
    resp = await client.post(
        f"/api/v1/consultations/{c.id}/messages",
        json={"body": "uninvited reply"},
        headers=_hdr(sub="outsider"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_consultation_reply_to_closed_consultation_409(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "REP-5")
    c = await _seed_consultation(db_session, "REP-5", status="closed")
    resp = await client.post(
        f"/api/v1/consultations/{c.id}/messages",
        json={"body": "late reply"},
        headers=_hdr(sub="dr-a"),
    )
    assert resp.status_code == 409


# ── Close ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consultation_close_by_sender_204(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CLO-1")
    c = await _seed_consultation(db_session, "CLO-1", from_id="dr-a", to_id="dr-b")
    resp = await client.patch(
        f"/api/v1/consultations/{c.id}/close",
        headers=_hdr(sub="dr-a"),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_consultation_close_sets_status_closed(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CLO-2")
    c = await _seed_consultation(db_session, "CLO-2", from_id="dr-a", to_id="dr-b")
    resp = await client.patch(
        f"/api/v1/consultations/{c.id}/close",
        headers=_hdr(sub="dr-a"),
    )
    assert resp.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_consultation_close_by_recipient_403(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CLO-3")
    c = await _seed_consultation(db_session, "CLO-3", from_id="dr-a", to_id="dr-b")
    resp = await client.patch(
        f"/api/v1/consultations/{c.id}/close",
        headers=_hdr(sub="dr-b"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_consultation_close_already_closed_idempotent(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "CLO-4")
    c = await _seed_consultation(db_session, "CLO-4", from_id="dr-a", status="closed")
    resp = await client.patch(
        f"/api/v1/consultations/{c.id}/close",
        headers=_hdr(sub="dr-a"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


# ── Patient list tab integration ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_list_tab_consulted_includes_consultation_patient(
    client: AsyncClient, db_session: AsyncSession
):
    """Doctor B's 'consulted' tab shows patients where B is a recipient of open consultations."""
    await _seed_patient(db_session, "TAB-1")
    # dr-a sends consultation to dr-b about TAB-1
    await _seed_consultation(db_session, "TAB-1", from_id="dr-a", to_id="dr-b", status="open")
    resp = await client.get(
        "/api/v1/patients?tab=consulted",
        headers=_hdr(sub="dr-b"),
    )
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "TAB-1" in mrns
