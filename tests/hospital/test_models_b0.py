"""Phase B0 — ORM model constraint tests.

Each test targets exactly one model or constraint.
All tests use an isolated in-memory SQLite DB with FK enforcement enabled.
Gate: pytest tests/hospital/test_models_b0.py --asyncio-mode=auto -x -q
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hospital.db.models import (
    Base,
    CareTeamMember,
    Consultation,
    ConsultationMessage,
    HisSyncEvent,
    MtdCase,
    MtdSession,
    Patient,
    PushSubscription,
    Reminder,
    TimelineEvent,
)
from hospital.db.session import _enable_sqlite_fk


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    _enable_sqlite_fk(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _patient(mrn: str = "MRN-001", status: str = "active", **kw) -> Patient:
    return Patient(
        mrn=mrn,
        masked_name="王●●",
        status=status,
        created_by="user-001",
        **kw,
    )


# ── Patient ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_create_and_retrieve(session: AsyncSession):
    p = _patient(mrn="MRN-A01", sex="F", dob_year=1975, his_patient_id="HIS-99")
    session.add(p)
    await session.flush()
    fetched = await session.get(Patient, "MRN-A01")
    assert fetched is not None
    assert fetched.masked_name == "王●●"
    assert fetched.his_patient_id == "HIS-99"


@pytest.mark.asyncio
async def test_patient_mrn_is_primary_key(session: AsyncSession):
    session.add(_patient("MRN-DUP"))
    await session.flush()
    session.add(_patient("MRN-DUP"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_patient_status_constraint_rejects_invalid(session: AsyncSession):
    session.add(_patient("MRN-BAD", status="unknown"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── CareTeamMember ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_care_team_unique_constraint(session: AsyncSession):
    session.add(_patient("MRN-CT1"))
    await session.flush()
    session.add(CareTeamMember(patient_mrn="MRN-CT1", user_id="u1", member_role="primary_hcp", assigned_by="u1"))
    await session.flush()
    session.add(CareTeamMember(patient_mrn="MRN-CT1", user_id="u1", member_role="consultant", assigned_by="u1"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_care_team_member_roles_constraint(session: AsyncSession):
    session.add(_patient("MRN-CT2"))
    await session.flush()
    session.add(CareTeamMember(patient_mrn="MRN-CT2", user_id="u2", member_role="nurse", assigned_by="u2"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── TimelineEvent ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_event_all_types_accepted(session: AsyncSession):
    session.add(_patient("MRN-TL1"))
    await session.flush()
    valid_types = [
        "his_sync", "doctor_note", "coordinator_note", "alert",
        "consultation_reply", "mtd_conclusion", "onco_query_initiated", "drug_reminder",
    ]
    for i, t in enumerate(valid_types):
        session.add(TimelineEvent(
            patient_mrn="MRN-TL1",
            event_type=t,
            source="manual",
            title=f"event {i}",
        ))
    await session.flush()
    result = await session.execute(
        text("SELECT COUNT(*) FROM timeline_events WHERE patient_mrn='MRN-TL1'")
    )
    assert result.scalar() == len(valid_types)


@pytest.mark.asyncio
async def test_timeline_event_invalid_type_rejected(session: AsyncSession):
    session.add(_patient("MRN-TL2"))
    await session.flush()
    session.add(TimelineEvent(
        patient_mrn="MRN-TL2",
        event_type="unknown",
        source="manual",
        title="bad",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── Consultation / ConsultationMessage ────────────────────────────────────────

@pytest.mark.asyncio
async def test_consultation_status_transitions(session: AsyncSession):
    session.add(_patient("MRN-CS1"))
    await session.flush()
    for status in ("open", "replied", "closed"):
        c = Consultation(
            patient_mrn="MRN-CS1",
            from_user_id="u1",
            to_user_id="u2",
            subject="Q",
            status=status,
        )
        session.add(c)
    await session.flush()


@pytest.mark.asyncio
async def test_consultation_message_cascade_delete(session: AsyncSession):
    session.add(_patient("MRN-CS2"))
    await session.flush()
    c = Consultation(
        patient_mrn="MRN-CS2",
        from_user_id="u1",
        to_user_id="u2",
        subject="Q",
        status="open",
    )
    session.add(c)
    await session.flush()
    msg = ConsultationMessage(consultation_id=c.id, sender_id="u1", body="Hello")
    session.add(msg)
    await session.flush()
    await session.delete(c)
    await session.flush()
    result = await session.execute(
        text(f"SELECT COUNT(*) FROM consultation_messages WHERE consultation_id='{c.id}'")
    )
    assert result.scalar() == 0


# ── Reminder ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reminder_type_constraint(session: AsyncSession):
    session.add(_patient("MRN-REM1"))
    await session.flush()
    valid_types = [
        "drug_reapplication", "pending_lab", "imaging_due",
        "followup_appt", "brca_result", "custom",
    ]
    for i, rt in enumerate(valid_types):
        session.add(Reminder(
            patient_mrn="MRN-REM1",
            reminder_type=rt,
            urgency="normal",
            title=f"rem {i}",
            due_date=_now(),
            triggered_by="rule_engine",
        ))
    await session.flush()


@pytest.mark.asyncio
async def test_reminder_status_constraint(session: AsyncSession):
    session.add(_patient("MRN-REM2"))
    await session.flush()
    session.add(Reminder(
        patient_mrn="MRN-REM2",
        reminder_type="custom",
        urgency="normal",
        title="bad status",
        due_date=_now(),
        triggered_by="rule_engine",
        status="ignored",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── PushSubscription ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_subscription_endpoint_unique(session: AsyncSession):
    session.add(PushSubscription(
        user_id="u1",
        endpoint="https://fcm.example/sub/abc",
        p256dh_key="k1",
        auth_key="a1",
    ))
    await session.flush()
    session.add(PushSubscription(
        user_id="u2",
        endpoint="https://fcm.example/sub/abc",
        p256dh_key="k2",
        auth_key="a2",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── MtdSession / MtdCase ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mtd_session_status_constraint(session: AsyncSession):
    session.add(MtdSession(
        meeting_date=_now(),
        created_by="u1",
        status="cancelled",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_mtd_case_unique_per_session(session: AsyncSession):
    session.add(_patient("MRN-MTD1"))
    await session.flush()
    mtd = MtdSession(meeting_date=_now(), created_by="u1", status="scheduled")
    session.add(mtd)
    await session.flush()
    session.add(MtdCase(mtd_session_id=mtd.id, patient_mrn="MRN-MTD1", added_by="u1"))
    await session.flush()
    session.add(MtdCase(mtd_session_id=mtd.id, patient_mrn="MRN-MTD1", added_by="u1"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── HisSyncEvent ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_his_sync_event_type_constraint(session: AsyncSession):
    session.add(_patient("MRN-HIS1"))
    await session.flush()
    session.add(HisSyncEvent(
        patient_mrn="MRN-HIS1",
        his_event_type="vitals",
        payload_json="{}",
        sync_source="his_adapter_mock",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── Meta ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_new_tables_created_via_create_all(session: AsyncSession):
    expected_tables = {
        "patients", "care_team_members", "timeline_events",
        "consultations", "consultation_messages", "reminders",
        "push_subscriptions", "mtd_sessions", "mtd_cases", "his_sync_events",
    }
    result = await session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    existing = {row[0] for row in result.fetchall()}
    assert expected_tables.issubset(existing), f"Missing tables: {expected_tables - existing}"


@pytest.mark.asyncio
async def test_foreign_key_patient_mrn_enforced(session: AsyncSession):
    session.add(CareTeamMember(
        patient_mrn="MRN-GHOST-999",
        user_id="u1",
        member_role="primary_hcp",
        assigned_by="u1",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
