"""Patient registry service — B1 business logic."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hospital.db.models import (
    CareTeamMember,
    Consultation,
    HisSyncEvent,
    MtdCase,
    MtdSession,
    Patient,
    Reminder,
)
from hospital.decision.schemas.patient import (
    CareTeamMemberCreate,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    CareTeamMemberResponse,
)


# ── Read helpers ──────────────────────────────────────────────────────────────

async def _active_team_mrns(db: AsyncSession, user_id: str) -> set[str]:
    rows = await db.scalars(
        select(CareTeamMember.patient_mrn).where(
            CareTeamMember.user_id == user_id,
            CareTeamMember.active.is_(True),
        )
    )
    return set(rows.all())


async def _primary_mrns(db: AsyncSession, user_id: str) -> set[str]:
    rows = await db.scalars(
        select(Patient.mrn).where(Patient.primary_doctor_id == user_id)
    )
    return set(rows.all())


async def _reminder_counts(
    db: AsyncSession, mrns: list[str]
) -> tuple[dict[str, int], dict[str, int]]:
    """Return (active_count_by_mrn, urgent_count_by_mrn)."""
    if not mrns:
        return {}, {}
    rows = await db.scalars(
        select(Reminder).where(
            Reminder.patient_mrn.in_(mrns),
            Reminder.status == "active",
        )
    )
    active: dict[str, int] = defaultdict(int)
    urgent: dict[str, int] = defaultdict(int)
    for r in rows.all():
        active[r.patient_mrn] += 1
        if r.urgency in ("high", "critical"):
            urgent[r.patient_mrn] += 1
    return dict(active), dict(urgent)


async def _patients_by_mrns(
    db: AsyncSession, mrns: list[str]
) -> list[Patient]:
    if not mrns:
        return []
    result = await db.scalars(
        select(Patient)
        .where(Patient.mrn.in_(mrns))
        .options(selectinload(Patient.care_team))
        .order_by(Patient.updated_at.desc())
    )
    return list(result.all())


async def _build_response(patient: Patient, active: int, urgent: int) -> PatientResponse:
    from datetime import datetime, timedelta, timezone as _tz
    _cutoff = datetime.now(_tz.utc) - timedelta(days=3)
    if not patient.his_patient_id:
        his_sync_status = "unknown"
    elif patient.his_synced_at is None:
        his_sync_status = "never"
    elif patient.his_synced_at < _cutoff:
        his_sync_status = "stale"
    else:
        his_sync_status = "ok"
    return PatientResponse(
        mrn=patient.mrn,
        masked_name=patient.masked_name,
        sex=patient.sex,
        dob_year=patient.dob_year,
        disease_summary=patient.disease_summary,
        status=patient.status,
        primary_doctor_id=patient.primary_doctor_id,
        his_patient_id=patient.his_patient_id,
        his_synced_at=patient.his_synced_at,
        active_reminder_count=active,
        urgent_reminder_count=urgent,
        his_sync_status=his_sync_status,
        care_team=[
            CareTeamMemberResponse.model_validate(m)
            for m in patient.care_team
            if m.active
        ],
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


# ── List patients ─────────────────────────────────────────────────────────────

TabLiteral = Literal["all", "followup", "consulted", "mtd", "alerts"]


async def list_patients(
    db: AsyncSession,
    user_id: str,
    tab: TabLiteral = "all",
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PatientResponse], int]:
    if tab == "followup":
        own = (await _primary_mrns(db, user_id)) | (await _active_team_mrns(db, user_id))
        appt_rows = await db.scalars(
            select(HisSyncEvent.patient_mrn).where(
                HisSyncEvent.patient_mrn.in_(list(own)),
                HisSyncEvent.his_event_type == "appointment",
            ).distinct()
        )
        mrns = [m for m in appt_rows.all() if m is not None]
    elif tab == "consulted":
        mrn_rows = await db.scalars(
            select(Consultation.patient_mrn).where(
                Consultation.to_user_id == user_id,
                Consultation.status == "open",
            ).distinct()
        )
        mrns = list(set(mrn_rows.all()))
    elif tab == "mtd":
        mrn_rows = await db.scalars(
            select(MtdCase.patient_mrn)
            .join(MtdSession, MtdCase.mtd_session_id == MtdSession.id)
            .where(MtdSession.status == "scheduled")
            .distinct()
        )
        mrns = list(set(mrn_rows.all()))
    elif tab == "alerts":
        own = (await _primary_mrns(db, user_id)) | (await _active_team_mrns(db, user_id))
        urgent_rows = await db.scalars(
            select(Reminder.patient_mrn).where(
                Reminder.patient_mrn.in_(list(own)),
                Reminder.status == "active",
                Reminder.urgency.in_(["high", "critical"]),
            ).distinct()
        )
        mrns = list(set(urgent_rows.all()))
    else:  # all
        mrns = list(
            (await _primary_mrns(db, user_id)) | (await _active_team_mrns(db, user_id))
        )

    patients = await _patients_by_mrns(db, mrns)
    if q:
        ql = q.lower()
        patients = [
            p for p in patients
            if ql in (p.mrn or "").lower()
            or ql in (p.masked_name or "").lower()
            or ql in (p.disease_summary or "").lower()
        ]
    total = len(patients)
    patients = patients[offset : offset + limit]
    active_map, urgent_map = await _reminder_counts(db, [p.mrn for p in patients])
    results = [
        await _build_response(p, active_map.get(p.mrn, 0), urgent_map.get(p.mrn, 0))
        for p in patients
    ]
    return results, total


# ── Get single patient ────────────────────────────────────────────────────────

async def get_patient(db: AsyncSession, mrn: str) -> Patient:
    result = await db.scalar(
        select(Patient)
        .where(Patient.mrn == mrn)
        .options(selectinload(Patient.care_team))
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PATIENT_NOT_FOUND", "message": f"MRN {mrn!r} not found."},
        )
    return result


async def is_on_care_team(db: AsyncSession, mrn: str, user_id: str) -> bool:
    row = await db.scalar(
        select(CareTeamMember).where(
            CareTeamMember.patient_mrn == mrn,
            CareTeamMember.user_id == user_id,
            CareTeamMember.active.is_(True),
        )
    )
    return row is not None


async def build_patient_response(db: AsyncSession, patient: Patient) -> PatientResponse:
    # Re-fetch with eager load so care_team relationship is available outside greenlet
    loaded = await get_patient(db, patient.mrn)
    active_map, urgent_map = await _reminder_counts(db, [loaded.mrn])
    return await _build_response(
        loaded,
        active_map.get(loaded.mrn, 0),
        urgent_map.get(loaded.mrn, 0),
    )


# ── Create patient ────────────────────────────────────────────────────────────

async def create_patient(
    db: AsyncSession,
    body: PatientCreate,
    user_id: str,
) -> Patient:
    existing = await db.scalar(select(Patient).where(Patient.mrn == body.mrn))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "PATIENT_ALREADY_EXISTS", "message": f"MRN {body.mrn!r} already registered."},
        )
    patient = Patient(
        mrn=body.mrn,
        masked_name=body.masked_name,
        sex=body.sex,
        dob_year=body.dob_year,
        disease_summary=body.disease_summary,
        status=body.status,
        primary_doctor_id=user_id,
        created_by=user_id,
    )
    db.add(patient)
    await db.flush()
    # Automatically add creator as primary_hcp
    db.add(CareTeamMember(
        patient_mrn=patient.mrn,
        user_id=user_id,
        member_role="primary_hcp",
        assigned_by=user_id,
    ))
    await db.flush()
    return patient


# ── Update patient ────────────────────────────────────────────────────────────

async def update_patient(
    db: AsyncSession,
    mrn: str,
    body: PatientUpdate,
) -> Patient:
    patient = await get_patient(db, mrn)
    if body.disease_summary is not None:
        patient.disease_summary = body.disease_summary
    if body.status is not None:
        patient.status = body.status
    await db.flush()
    return patient


# ── Care team ─────────────────────────────────────────────────────────────────

async def require_primary_doctor(db: AsyncSession, mrn: str, user_id: str) -> Patient:
    patient = await get_patient(db, mrn)
    if patient.primary_doctor_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "NOT_PRIMARY_DOCTOR", "message": "Only the primary doctor can manage the care team."},
        )
    return patient


async def list_care_team(db: AsyncSession, mrn: str) -> list[CareTeamMember]:
    await get_patient(db, mrn)  # ensure patient exists
    result = await db.scalars(
        select(CareTeamMember)
        .where(CareTeamMember.patient_mrn == mrn)
        .order_by(CareTeamMember.assigned_at)
    )
    return list(result.all())


async def add_care_team_member(
    db: AsyncSession,
    mrn: str,
    body: CareTeamMemberCreate,
    assigned_by: str,
) -> CareTeamMember:
    existing = await db.scalar(
        select(CareTeamMember).where(
            CareTeamMember.patient_mrn == mrn,
            CareTeamMember.user_id == body.user_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "ALREADY_ON_TEAM", "message": f"User {body.user_id!r} already on care team."},
        )
    if body.member_role == "care_coordinator":
        existing_coord = await db.scalar(
            select(CareTeamMember).where(
                CareTeamMember.patient_mrn == mrn,
                CareTeamMember.member_role == "care_coordinator",
                CareTeamMember.active.is_(True),
            )
        )
        if existing_coord:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "COORDINATOR_ALREADY_EXISTS", "message": "A care coordinator is already assigned."},
            )
    member = CareTeamMember(
        patient_mrn=mrn,
        user_id=body.user_id,
        member_role=body.member_role,
        specialty=body.specialty,
        assigned_by=assigned_by,
    )
    db.add(member)
    await db.flush()
    return member


async def remove_care_team_member(
    db: AsyncSession,
    mrn: str,
    target_user_id: str,
) -> None:
    member = await db.scalar(
        select(CareTeamMember).where(
            CareTeamMember.patient_mrn == mrn,
            CareTeamMember.user_id == target_user_id,
            CareTeamMember.active.is_(True),
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MEMBER_NOT_FOUND", "message": f"User {target_user_id!r} is not an active member."},
        )
    member.active = False
    await db.flush()
