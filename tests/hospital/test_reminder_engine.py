"""Phase B4 — Reminder engine tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import DrugRequisition, HisSyncEvent, Patient, Reminder
from hospital.decision.services import reminder_rules as rules
from hospital.decision.services.reminder_service import evaluate_patient
from tests.hospital.conftest import make_jwt


def _now():
    return datetime.now(timezone.utc)


def _hdr(role="clinic_hcp", sub="user-001"):
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


async def _seed(db: AsyncSession, mrn: str = "REM-P1") -> Patient:
    p = Patient(mrn=mrn, masked_name="R●●", status="active",
                primary_doctor_id="user-001", created_by="user-001")
    db.add(p)
    await db.flush()
    return p


# ── Rule: drug_reapplication ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_drug_reapplication_14d_creates_reminder(db_session: AsyncSession):
    await _seed(db_session, "DR-1")
    expires = _now() + timedelta(days=10)
    db_session.add(DrugRequisition(
        mrn="DR-1", track_id="t1",
        requisition_json=json.dumps({"expires_at": expires.isoformat()}),
        created_by="u1", status="approved",
    ))
    await db_session.flush()
    r = await rules.rule_drug_reapplication_14d(db_session, "DR-1")
    assert r is not None
    assert r.reminder_type == "drug_reapplication"
    assert r.urgency == "normal"


@pytest.mark.asyncio
async def test_rule_drug_reapplication_3d_creates_reminder_with_high_urgency(
    db_session: AsyncSession,
):
    await _seed(db_session, "DR-2")
    expires = _now() + timedelta(days=2)
    db_session.add(DrugRequisition(
        mrn="DR-2", track_id="t1",
        requisition_json=json.dumps({"expires_at": expires.isoformat()}),
        created_by="u1", status="approved",
    ))
    await db_session.flush()
    r = await rules.rule_drug_reapplication_3d(db_session, "DR-2")
    assert r is not None
    assert r.urgency == "high"


@pytest.mark.asyncio
async def test_rule_drug_reapplication_no_duplicate_if_active_reminder_exists(
    db_session: AsyncSession,
):
    await _seed(db_session, "DR-3")
    expires = _now() + timedelta(days=10)
    db_session.add(DrugRequisition(
        mrn="DR-3", track_id="t1",
        requisition_json=json.dumps({"expires_at": expires.isoformat()}),
        created_by="u1", status="approved",
    ))
    await db_session.flush()
    r1 = await rules.rule_drug_reapplication_14d(db_session, "DR-3")
    assert r1 is not None
    r2 = await rules.rule_drug_reapplication_14d(db_session, "DR-3")
    assert r2 is None  # duplicate suppressed


@pytest.mark.asyncio
async def test_rule_drug_reapplication_no_reminder_if_expiry_far_away(
    db_session: AsyncSession,
):
    await _seed(db_session, "DR-4")
    expires = _now() + timedelta(days=30)
    db_session.add(DrugRequisition(
        mrn="DR-4", track_id="t1",
        requisition_json=json.dumps({"expires_at": expires.isoformat()}),
        created_by="u1", status="approved",
    ))
    await db_session.flush()
    r = await rules.rule_drug_reapplication_14d(db_session, "DR-4")
    assert r is None


# ── Rule: BRCA pending ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_brca_pending_creates_reminder_after_14_days(db_session: AsyncSession):
    await _seed(db_session, "BRCA-1")
    old_time = _now() - timedelta(days=15)
    db_session.add(HisSyncEvent(
        patient_mrn="BRCA-1", raw_mrn="BRCA-1",
        his_event_type="lab_result",
        payload_json=json.dumps({"lab_type": "BRCA", "ordered": True}),
        sync_source="test",
        received_at=old_time,
    ))
    await db_session.flush()
    r = await rules.rule_brca_pending_14d(db_session, "BRCA-1")
    assert r is not None
    assert r.reminder_type == "brca_result"


@pytest.mark.asyncio
async def test_rule_brca_pending_no_reminder_if_result_received(db_session: AsyncSession):
    await _seed(db_session, "BRCA-2")
    old_time = _now() - timedelta(days=15)
    new_time = _now() - timedelta(days=3)
    db_session.add(HisSyncEvent(
        patient_mrn="BRCA-2", raw_mrn="BRCA-2",
        his_event_type="lab_result",
        payload_json=json.dumps({"lab_type": "BRCA", "ordered": True}),
        sync_source="test", received_at=old_time,
    ))
    db_session.add(HisSyncEvent(
        patient_mrn="BRCA-2", raw_mrn="BRCA-2",
        his_event_type="lab_result",
        payload_json=json.dumps({"lab_type": "BRCA", "result": "negative"}),
        sync_source="test", received_at=new_time,
    ))
    await db_session.flush()
    r = await rules.rule_brca_pending_14d(db_session, "BRCA-2")
    assert r is None


@pytest.mark.asyncio
async def test_rule_brca_pending_no_reminder_within_14_days(db_session: AsyncSession):
    await _seed(db_session, "BRCA-3")
    recent_time = _now() - timedelta(days=5)
    db_session.add(HisSyncEvent(
        patient_mrn="BRCA-3", raw_mrn="BRCA-3",
        his_event_type="lab_result",
        payload_json=json.dumps({"lab_type": "BRCA", "ordered": True}),
        sync_source="test", received_at=recent_time,
    ))
    await db_session.flush()
    r = await rules.rule_brca_pending_14d(db_session, "BRCA-3")
    assert r is None


# ── Rule: imaging followup ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_imaging_followup_creates_reminder_7_days_before(
    db_session: AsyncSession,
):
    await _seed(db_session, "IMG-1")
    exam_date = _now() + timedelta(days=5)
    db_session.add(HisSyncEvent(
        patient_mrn="IMG-1", raw_mrn="IMG-1",
        his_event_type="appointment",
        payload_json=json.dumps({"exam_type": "imaging", "exam_date": exam_date.isoformat()}),
        sync_source="test",
    ))
    await db_session.flush()
    r = await rules.rule_imaging_followup_due(db_session, "IMG-1")
    assert r is not None
    assert r.reminder_type == "imaging_due"


@pytest.mark.asyncio
async def test_rule_imaging_followup_no_reminder_if_already_booked(
    db_session: AsyncSession,
):
    await _seed(db_session, "IMG-2")
    exam_date = _now() + timedelta(days=5)
    db_session.add(HisSyncEvent(
        patient_mrn="IMG-2", raw_mrn="IMG-2",
        his_event_type="appointment",
        payload_json=json.dumps({
            "exam_type": "imaging", "exam_date": exam_date.isoformat(), "booked": True
        }),
        sync_source="test",
    ))
    await db_session.flush()
    r = await rules.rule_imaging_followup_due(db_session, "IMG-2")
    assert r is None


# ── Rule: followup appointment ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_followup_appt_creates_reminder_7d_before(db_session: AsyncSession):
    await _seed(db_session, "APPT-1")
    appt_date = _now() + timedelta(days=4)
    db_session.add(HisSyncEvent(
        patient_mrn="APPT-1", raw_mrn="APPT-1",
        his_event_type="appointment",
        payload_json=json.dumps({"appt_date": appt_date.isoformat()}),
        sync_source="test",
    ))
    await db_session.flush()
    r = await rules.rule_followup_appt_7d(db_session, "APPT-1")
    assert r is not None
    assert r.reminder_type == "followup_appt"


@pytest.mark.asyncio
async def test_rule_followup_appt_no_reminder_if_no_upcoming_appt(
    db_session: AsyncSession,
):
    await _seed(db_session, "APPT-2")
    # no HisSyncEvent for this patient
    r = await rules.rule_followup_appt_7d(db_session, "APPT-2")
    assert r is None


# ── Rule: auto expire ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_auto_expire_marks_past_due_reminders_expired(
    db_session: AsyncSession,
):
    await _seed(db_session, "EXP-1")
    past_due = _now() - timedelta(hours=1)
    db_session.add(Reminder(
        patient_mrn="EXP-1", reminder_type="custom", urgency="normal",
        title="old", due_date=past_due, triggered_by="test", status="active",
    ))
    await db_session.flush()
    count = await rules.rule_auto_expire(db_session, "EXP-1")
    assert count == 1


@pytest.mark.asyncio
async def test_rule_auto_expire_does_not_touch_acknowledged_reminders(
    db_session: AsyncSession,
):
    await _seed(db_session, "EXP-2")
    past_due = _now() - timedelta(hours=1)
    db_session.add(Reminder(
        patient_mrn="EXP-2", reminder_type="custom", urgency="normal",
        title="acked", due_date=past_due, triggered_by="test", status="acknowledged",
    ))
    await db_session.flush()
    count = await rules.rule_auto_expire(db_session, "EXP-2")
    assert count == 0


# ── Service layer ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reminder_service_evaluate_all_rules_for_patient(
    db_session: AsyncSession,
):
    await _seed(db_session, "SVC-1")
    expires = _now() + timedelta(days=2)
    db_session.add(DrugRequisition(
        mrn="SVC-1", track_id="t1",
        requisition_json=json.dumps({"expires_at": expires.isoformat()}),
        created_by="u1", status="approved",
    ))
    await db_session.flush()
    fired = await evaluate_patient(db_session, "SVC-1")
    assert any("drug_reapplication" in f for f in fired)


@pytest.mark.asyncio
async def test_reminder_service_no_duplicate_active_reminder_same_type_and_patient(
    db_session: AsyncSession,
):
    await _seed(db_session, "SVC-2")
    expires = _now() + timedelta(days=10)
    db_session.add(DrugRequisition(
        mrn="SVC-2", track_id="t1",
        requisition_json=json.dumps({"expires_at": expires.isoformat()}),
        created_by="u1", status="approved",
    ))
    await db_session.flush()
    await evaluate_patient(db_session, "SVC-2")
    await evaluate_patient(db_session, "SVC-2")
    from sqlalchemy import select, func
    count = await db_session.scalar(
        select(func.count()).select_from(Reminder).where(
            Reminder.patient_mrn == "SVC-2",
            Reminder.triggered_by == "drug_reapplication_14d",
        )
    )
    assert count == 1


# ── API: list ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reminder_list_returns_active_reminders(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "RAPI-1")
    db_session.add(Reminder(
        patient_mrn="RAPI-1", reminder_type="custom", urgency="normal",
        title="test", due_date=_now() + timedelta(days=1),
        triggered_by="test", status="active",
    ))
    await db_session.flush()
    resp = await client.get("/api/v1/patients/RAPI-1/reminders", headers=_hdr())
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_reminder_list_filter_status_active(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "RAPI-2")
    db_session.add_all([
        Reminder(patient_mrn="RAPI-2", reminder_type="custom", urgency="normal",
                 title="active", due_date=_now() + timedelta(days=1),
                 triggered_by="t1", status="active"),
        Reminder(patient_mrn="RAPI-2", reminder_type="custom", urgency="normal",
                 title="expired", due_date=_now() - timedelta(days=1),
                 triggered_by="t2", status="expired"),
    ])
    await db_session.flush()
    resp = await client.get("/api/v1/patients/RAPI-2/reminders?reminder_status=active", headers=_hdr())
    assert resp.status_code == 200
    assert all(r["status"] == "active" for r in resp.json())


@pytest.mark.asyncio
async def test_reminder_list_filter_status_expired(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "RAPI-3")
    db_session.add(Reminder(
        patient_mrn="RAPI-3", reminder_type="custom", urgency="normal",
        title="expired", due_date=_now() - timedelta(days=1),
        triggered_by="t1", status="expired",
    ))
    await db_session.flush()
    resp = await client.get("/api/v1/patients/RAPI-3/reminders?reminder_status=expired", headers=_hdr())
    assert resp.status_code == 200
    assert all(r["status"] == "expired" for r in resp.json())


@pytest.mark.asyncio
async def test_reminder_list_unknown_mrn_404(client: AsyncClient):
    resp = await client.get("/api/v1/patients/GHOST-MRN/reminders", headers=_hdr())
    assert resp.status_code == 404


# ── API: acknowledge ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reminder_acknowledge_sets_status_acknowledged(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "ACK-1")
    r = Reminder(
        patient_mrn="ACK-1", reminder_type="custom", urgency="normal",
        title="ack me", due_date=_now() + timedelta(days=1),
        triggered_by="t1", status="active",
    )
    db_session.add(r)
    await db_session.flush()
    resp = await client.patch(
        f"/api/v1/patients/ACK-1/reminders/{r.id}/acknowledge", headers=_hdr()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_reminder_acknowledge_sets_acknowledged_by_and_at(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "ACK-2")
    r = Reminder(
        patient_mrn="ACK-2", reminder_type="custom", urgency="normal",
        title="ack", due_date=_now() + timedelta(days=1),
        triggered_by="t1", status="active",
    )
    db_session.add(r)
    await db_session.flush()
    resp = await client.patch(
        f"/api/v1/patients/ACK-2/reminders/{r.id}/acknowledge", headers=_hdr("clinic_hcp", "dr-acker")
    )
    assert resp.status_code == 200
    assert resp.json()["acknowledged_by"] == "dr-acker"
    assert resp.json()["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_reminder_acknowledge_already_acknowledged_idempotent(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "ACK-3")
    r = Reminder(
        patient_mrn="ACK-3", reminder_type="custom", urgency="normal",
        title="ack", due_date=_now() + timedelta(days=1),
        triggered_by="t1", status="active",
    )
    db_session.add(r)
    await db_session.flush()
    await client.patch(f"/api/v1/patients/ACK-3/reminders/{r.id}/acknowledge", headers=_hdr())
    resp = await client.patch(f"/api/v1/patients/ACK-3/reminders/{r.id}/acknowledge", headers=_hdr())
    assert resp.status_code == 200  # idempotent


@pytest.mark.asyncio
async def test_reminder_acknowledge_unknown_id_404(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "ACK-4")
    resp = await client.patch(
        "/api/v1/patients/ACK-4/reminders/ghost-id/acknowledge", headers=_hdr()
    )
    assert resp.status_code == 404


# ── API: custom create ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reminder_custom_create_201(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, "CUS-1")
    future = (_now() + timedelta(days=3)).isoformat()
    resp = await client.post(
        "/api/v1/patients/CUS-1/reminders",
        json={"title": "自訂提醒", "due_date": future},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    assert resp.json()["reminder_type"] == "custom"


@pytest.mark.asyncio
async def test_reminder_custom_create_missing_title_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "CUS-2")
    future = (_now() + timedelta(days=3)).isoformat()
    resp = await client.post(
        "/api/v1/patients/CUS-2/reminders",
        json={"due_date": future},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reminder_custom_create_past_due_date_422(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "CUS-3")
    past = (_now() - timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/v1/patients/CUS-3/reminders",
        json={"title": "過期提醒", "due_date": past},
        headers=_hdr(),
    )
    assert resp.status_code == 422


# ── API: force evaluate ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reminder_admin_evaluate_runs_all_rules(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "EVAL-1")
    resp = await client.post(
        "/api/v1/admin/reminders/evaluate",
        headers={"Authorization": f"Bearer {make_jwt(role='kb_admin', sub='admin-001')}"},
    )
    assert resp.status_code == 200
    assert "evaluated" in resp.json()


@pytest.mark.asyncio
async def test_reminder_admin_evaluate_requires_kb_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/admin/reminders/evaluate",
        headers=_hdr("clinic_hcp"),
    )
    assert resp.status_code == 403
