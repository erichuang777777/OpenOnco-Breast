"""Phase B6 — MTD management tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import CareTeamMember, MtdCase, MtdSession, Patient, TimelineEvent
from tests.hospital.conftest import make_jwt


def _now():
    return datetime.now(timezone.utc)


def _hdr(role: str = "tumor_board_hcp", sub: str = "board-dr") -> dict:
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


def _hcp(sub: str = "hcp-001") -> dict:
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role='clinic_hcp')}"}


async def _seed_patient(db: AsyncSession, mrn: str) -> Patient:
    p = Patient(mrn=mrn, masked_name="M●●", status="active",
                primary_doctor_id="board-dr", created_by="board-dr")
    db.add(p)
    await db.flush()
    return p


async def _seed_coordinator(db: AsyncSession, mrn: str, coord_id: str = "coord-001") -> CareTeamMember:
    m = CareTeamMember(
        patient_mrn=mrn,
        user_id=coord_id,
        member_role="care_coordinator",
        assigned_by="board-dr",
    )
    db.add(m)
    await db.flush()
    return m


async def _seed_session(
    db: AsyncSession,
    days_offset: int = 3,
    status: str = "scheduled",
) -> MtdSession:
    s = MtdSession(
        meeting_date=_now() + timedelta(days=days_offset),
        location="Room 201",
        created_by="board-dr",
        status=status,
    )
    db.add(s)
    await db.flush()
    return s


# ── Session CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mtd_session_create_201(client: AsyncClient, db_session: AsyncSession):
    meeting_date = (_now() + timedelta(days=7)).isoformat()
    resp = await client.post(
        "/api/v1/mtd/sessions",
        json={"meeting_date": meeting_date, "location": "Meeting Room A"},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "scheduled"
    assert data["location"] == "Meeting Room A"


@pytest.mark.asyncio
async def test_mtd_session_create_requires_tumor_board_role(client: AsyncClient):
    meeting_date = (_now() + timedelta(days=7)).isoformat()
    resp = await client.post(
        "/api/v1/mtd/sessions",
        json={"meeting_date": meeting_date},
        headers=_hcp(),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mtd_session_list_returns_sessions(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_session(db_session)
    await _seed_session(db_session, days_offset=10)
    resp = await client.get("/api/v1/mtd/sessions", headers=_hcp())
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_mtd_session_list_filter_by_status(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_session(db_session, status="scheduled")
    await _seed_session(db_session, status="completed")
    resp = await client.get("/api/v1/mtd/sessions?status=scheduled", headers=_hcp())
    assert resp.status_code == 200
    assert all(s["status"] == "scheduled" for s in resp.json())


@pytest.mark.asyncio
async def test_mtd_session_get_unknown_404(client: AsyncClient):
    resp = await client.get("/api/v1/mtd/sessions/ghost-id", headers=_hcp())
    assert resp.status_code == 404


# ── Add case ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mtd_add_case_201(client: AsyncClient, db_session: AsyncSession):
    await _seed_patient(db_session, "MTD-P1")
    s = await _seed_session(db_session)
    resp = await client.post(
        f"/api/v1/mtd/sessions/{s.id}/cases",
        json={"patient_mrn": "MTD-P1", "reason": "complex case"},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    assert any(c["patient_mrn"] == "MTD-P1" for c in resp.json()["cases"])


@pytest.mark.asyncio
async def test_mtd_add_case_duplicate_409(client: AsyncClient, db_session: AsyncSession):
    await _seed_patient(db_session, "MTD-P2")
    s = await _seed_session(db_session)
    await client.post(
        f"/api/v1/mtd/sessions/{s.id}/cases",
        json={"patient_mrn": "MTD-P2"},
        headers=_hdr(),
    )
    resp = await client.post(
        f"/api/v1/mtd/sessions/{s.id}/cases",
        json={"patient_mrn": "MTD-P2"},
        headers=_hdr(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_mtd_add_case_unknown_mrn_404(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _seed_session(db_session)
    resp = await client.post(
        f"/api/v1/mtd/sessions/{s.id}/cases",
        json={"patient_mrn": "GHOST-MRN"},
        headers=_hdr(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mtd_add_case_unknown_session_404(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "MTD-P3")
    resp = await client.post(
        "/api/v1/mtd/sessions/ghost-session/cases",
        json={"patient_mrn": "MTD-P3"},
        headers=_hdr(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mtd_add_case_requires_tumor_board_role(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "MTD-P4")
    s = await _seed_session(db_session)
    resp = await client.post(
        f"/api/v1/mtd/sessions/{s.id}/cases",
        json={"patient_mrn": "MTD-P4"},
        headers=_hcp(),
    )
    assert resp.status_code == 403


# ── Conclude ──────────────────────────────────────────────────────────────────

async def _setup_conclude(db: AsyncSession, mrn: str, coord_id: str = "coord-001"):
    await _seed_patient(db, mrn)
    await _seed_coordinator(db, mrn, coord_id)
    s = await _seed_session(db)
    c = MtdCase(
        mtd_session_id=s.id,
        patient_mrn=mrn,
        added_by="board-dr",
    )
    db.add(c)
    await db.flush()
    return s


@pytest.mark.asyncio
async def test_mtd_conclude_sets_case_status_discussed(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _setup_conclude(db_session, "CON-1")
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-1/conclude",
        json={"conclusion_text": "繼續 THP", "case_status": "discussed"},
        headers=_hdr(role="clinic_hcp", sub="coord-001"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "discussed"


@pytest.mark.asyncio
async def test_mtd_conclude_sets_conclusion_by_and_at(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _setup_conclude(db_session, "CON-2")
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-2/conclude",
        json={"conclusion_text": "結論", "case_status": "discussed"},
        headers=_hdr(role="clinic_hcp", sub="coord-001"),
    )
    assert resp.json()["conclusion_by"] == "coord-001"
    assert resp.json()["conclusion_at"] is not None


@pytest.mark.asyncio
async def test_mtd_conclude_creates_timeline_event(
    client: AsyncClient, db_session: AsyncSession
):
    from sqlalchemy import select as sa_select

    s = await _setup_conclude(db_session, "CON-3")
    await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-3/conclude",
        json={"conclusion_text": "timeline check", "case_status": "discussed"},
        headers=_hdr(role="clinic_hcp", sub="coord-001"),
    )
    row = await db_session.scalar(
        sa_select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "CON-3",
            TimelineEvent.event_type == "mtd_conclusion",
        )
    )
    assert row is not None


@pytest.mark.asyncio
async def test_mtd_conclude_timeline_event_body_contains_conclusion_text(
    client: AsyncClient, db_session: AsyncSession
):
    from sqlalchemy import select as sa_select

    s = await _setup_conclude(db_session, "CON-4")
    await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-4/conclude",
        json={"conclusion_text": "結論文字測試", "case_status": "discussed"},
        headers=_hdr(role="clinic_hcp", sub="coord-001"),
    )
    row = await db_session.scalar(
        sa_select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "CON-4",
            TimelineEvent.event_type == "mtd_conclusion",
        )
    )
    assert row is not None
    body = json.loads(row.body_json)
    assert body["conclusion_text"] == "結論文字測試"


@pytest.mark.asyncio
async def test_mtd_conclude_timeline_event_body_contains_meeting_date(
    client: AsyncClient, db_session: AsyncSession
):
    from sqlalchemy import select as sa_select

    s = await _setup_conclude(db_session, "CON-5")
    await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-5/conclude",
        json={"conclusion_text": "meeting date test", "case_status": "discussed"},
        headers=_hdr(role="clinic_hcp", sub="coord-001"),
    )
    row = await db_session.scalar(
        sa_select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "CON-5",
            TimelineEvent.event_type == "mtd_conclusion",
        )
    )
    body = json.loads(row.body_json)
    assert "meeting_date" in body


@pytest.mark.asyncio
async def test_mtd_conclude_by_non_care_coordinator_403(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _setup_conclude(db_session, "CON-6")
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-6/conclude",
        json={"conclusion_text": "unauthorized", "case_status": "discussed"},
        headers=_hdr(role="clinic_hcp", sub="other-doctor"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mtd_conclude_deferred_status_stored(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _setup_conclude(db_session, "CON-7")
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-7/conclude",
        json={"conclusion_text": "延後討論", "case_status": "deferred"},
        headers=_hdr(role="clinic_hcp", sub="coord-001"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deferred"


@pytest.mark.asyncio
async def test_mtd_conclude_already_concluded_idempotent(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _setup_conclude(db_session, "CON-8")
    hdr = _hdr(role="clinic_hcp", sub="coord-001")
    await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-8/conclude",
        json={"conclusion_text": "first", "case_status": "discussed"},
        headers=hdr,
    )
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}/cases/CON-8/conclude",
        json={"conclusion_text": "second attempt", "case_status": "deferred"},
        headers=hdr,
    )
    assert resp.status_code == 200
    assert resp.json()["conclusion_text"] == "first"  # not overwritten


# ── Session status ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mtd_session_status_to_in_progress(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _seed_session(db_session)
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}",
        json={"status": "in_progress"},
        headers=_hdr(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_mtd_session_status_to_completed(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _seed_session(db_session)
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}",
        json={"status": "completed"},
        headers=_hdr(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_mtd_session_invalid_status_422(
    client: AsyncClient, db_session: AsyncSession
):
    s = await _seed_session(db_session)
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{s.id}",
        json={"status": "cancelled"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


# ── Patient list tab integration ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_list_tab_mtd_includes_patient_in_upcoming_session(
    client: AsyncClient, db_session: AsyncSession
):
    """Patients added to a scheduled MtdSession within 7 days appear in '待MTD' tab."""
    await _seed_patient(db_session, "MTAB-1")
    s = await _seed_session(db_session, days_offset=3, status="scheduled")
    c = MtdCase(
        mtd_session_id=s.id,
        patient_mrn="MTAB-1",
        added_by="board-dr",
    )
    db_session.add(c)
    await db_session.flush()
    resp = await client.get("/api/v1/patients?tab=mtd", headers=_hcp())
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "MTAB-1" in mrns
