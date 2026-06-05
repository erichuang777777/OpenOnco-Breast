"""Phase B2 — Timeline Events API tests."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import Patient, TimelineEvent
from hospital.decision.services import timeline_service
from tests.hospital.conftest import make_jwt


def _now():
    return datetime.now(timezone.utc)


def _hdr(sub="user-001", role="clinic_hcp"):
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


# ── Shared patient fixture ────────────────────────────────────────────────────

async def _seed_patient(db: AsyncSession, mrn: str = "TL-P1") -> Patient:
    p = Patient(mrn=mrn, masked_name="T●●", status="active",
                primary_doctor_id="user-001", created_by="user-001")
    db.add(p)
    await db.flush()
    return p


# ── list ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_list_returns_events_newest_first(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session)
    t1 = _now() - timedelta(hours=2)
    t2 = _now() - timedelta(hours=1)
    db_session.add_all([
        TimelineEvent(patient_mrn="TL-P1", event_type="doctor_note", source="manual",
                      title="older", event_time=t1),
        TimelineEvent(patient_mrn="TL-P1", event_type="doctor_note", source="manual",
                      title="newer", event_time=t2),
    ])
    await db_session.flush()
    resp = await client.get("/api/v1/patients/TL-P1/timeline", headers=_hdr())
    assert resp.status_code == 200
    titles = [e["title"] for e in resp.json()]
    assert titles.index("newer") < titles.index("older")


@pytest.mark.asyncio
async def test_timeline_list_filter_by_type(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-P2")
    db_session.add_all([
        TimelineEvent(patient_mrn="TL-P2", event_type="doctor_note", source="manual", title="A"),
        TimelineEvent(patient_mrn="TL-P2", event_type="his_sync", source="his_sync", title="B"),
    ])
    await db_session.flush()
    resp = await client.get("/api/v1/patients/TL-P2/timeline?type=doctor_note", headers=_hdr())
    assert resp.status_code == 200
    types = [e["event_type"] for e in resp.json()]
    assert all(t == "doctor_note" for t in types)
    assert len(types) == 1


@pytest.mark.asyncio
async def test_timeline_list_pagination(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-P3")
    for i in range(5):
        db_session.add(TimelineEvent(
            patient_mrn="TL-P3", event_type="doctor_note", source="manual",
            title=f"note {i}", event_time=_now() - timedelta(minutes=i),
        ))
    await db_session.flush()
    resp = await client.get("/api/v1/patients/TL-P3/timeline?limit=2&offset=0", headers=_hdr())
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    resp2 = await client.get("/api/v1/patients/TL-P3/timeline?limit=2&offset=2", headers=_hdr())
    assert len(resp2.json()) == 2


@pytest.mark.asyncio
async def test_timeline_list_unknown_mrn_404(client: AsyncClient):
    resp = await client.get("/api/v1/patients/GHOST-MRN/timeline", headers=_hdr())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_timeline_list_requires_auth(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-AUTH")
    resp = await client.get("/api/v1/patients/TL-AUTH/timeline")
    assert resp.status_code == 401


# ── create doctor_note ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_post_doctor_note_201(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-D1")
    resp = await client.post(
        "/api/v1/patients/TL-D1/timeline",
        json={"event_type": "doctor_note", "title": "C2 耐受性良好"},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    assert resp.json()["event_type"] == "doctor_note"


@pytest.mark.asyncio
async def test_timeline_post_sets_created_by_from_jwt(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-D2")
    resp = await client.post(
        "/api/v1/patients/TL-D2/timeline",
        json={"event_type": "doctor_note", "title": "note"},
        headers=_hdr("dr-author"),
    )
    assert resp.status_code == 201
    assert resp.json()["created_by"] == "dr-author"


@pytest.mark.asyncio
async def test_timeline_post_custom_event_time_accepted(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-D3")
    custom_time = "2026-01-15T08:00:00Z"
    resp = await client.post(
        "/api/v1/patients/TL-D3/timeline",
        json={"event_type": "doctor_note", "title": "old note", "event_time": custom_time},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    assert "2026-01-15" in resp.json()["event_time"]


@pytest.mark.asyncio
async def test_timeline_post_missing_title_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-D4")
    resp = await client.post(
        "/api/v1/patients/TL-D4/timeline",
        json={"event_type": "doctor_note"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timeline_post_empty_title_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-D5")
    resp = await client.post(
        "/api/v1/patients/TL-D5/timeline",
        json={"event_type": "doctor_note", "title": "   "},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timeline_post_unknown_mrn_404(client: AsyncClient):
    resp = await client.post(
        "/api/v1/patients/GHOST-MRN/timeline",
        json={"event_type": "doctor_note", "title": "note"},
        headers=_hdr(),
    )
    assert resp.status_code == 404


# ── create coordinator_note ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_post_coordinator_note_201(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-C1")
    resp = await client.post(
        "/api/v1/patients/TL-C1/timeline",
        json={"event_type": "coordinator_note", "title": "協調師備註"},
        headers=_hdr(),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_timeline_post_coordinator_note_type_stored(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-C2")
    resp = await client.post(
        "/api/v1/patients/TL-C2/timeline",
        json={"event_type": "coordinator_note", "title": "記錄"},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    assert resp.json()["event_type"] == "coordinator_note"


# ── system-only types rejected from API ──────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_post_his_sync_type_rejected_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-S1")
    resp = await client.post(
        "/api/v1/patients/TL-S1/timeline",
        json={"event_type": "his_sync", "title": "HIS"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timeline_post_alert_type_rejected_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-S2")
    resp = await client.post(
        "/api/v1/patients/TL-S2/timeline",
        json={"event_type": "alert", "title": "alert"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timeline_post_mtd_conclusion_type_rejected_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "TL-S3")
    resp = await client.post(
        "/api/v1/patients/TL-S3/timeline",
        json={"event_type": "mtd_conclusion", "title": "conclusion"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


# ── service layer direct tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_service_add_his_sync_event(db_session: AsyncSession):
    db_session.add(Patient(mrn="TL-SVC1", masked_name="S", status="active",
                           primary_doctor_id="u1", created_by="u1"))
    await db_session.flush()
    event = await timeline_service.add_system_event(
        db_session, "TL-SVC1", "his_sync", "HIS: 門診預約", source="his_sync"
    )
    assert event.event_type == "his_sync"
    assert event.source == "his_sync"
    assert event.created_by is None


@pytest.mark.asyncio
async def test_timeline_service_add_alert_event(db_session: AsyncSession):
    db_session.add(Patient(mrn="TL-SVC2", masked_name="S", status="active",
                           primary_doctor_id="u1", created_by="u1"))
    await db_session.flush()
    event = await timeline_service.add_system_event(
        db_session, "TL-SVC2", "alert", "藥物逾期提醒"
    )
    assert event.event_type == "alert"


@pytest.mark.asyncio
async def test_timeline_service_add_mtd_conclusion_event(db_session: AsyncSession):
    db_session.add(Patient(mrn="TL-SVC3", masked_name="S", status="active",
                           primary_doctor_id="u1", created_by="u1"))
    await db_session.flush()
    event = await timeline_service.add_system_event(
        db_session, "TL-SVC3", "mtd_conclusion", "MTD 結論：繼續 AC-T"
    )
    assert event.event_type == "mtd_conclusion"


@pytest.mark.asyncio
async def test_timeline_service_add_onco_query_event(db_session: AsyncSession):
    db_session.add(Patient(mrn="TL-SVC4", masked_name="S", status="active",
                           primary_doctor_id="u1", created_by="u1"))
    await db_session.flush()
    event = await timeline_service.add_system_event(
        db_session, "TL-SVC4", "onco_query_initiated", "醫師發起循證查詢"
    )
    assert event.event_type == "onco_query_initiated"
