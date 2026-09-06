"""MTD service — Phase B6."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hospital.db.models import CareTeamMember, MtdCase, MtdSession
from hospital.decision.schemas.mtd import (
    MtdCaseCreate,
    MtdCaseResponse,
    MtdConclude,
    MtdSessionCreate,
    MtdSessionResponse,
    MtdSessionStatusUpdate,
)
from hospital.decision.services.patient_service import get_patient
from hospital.decision.services.timeline_service import add_system_event


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_session(db: AsyncSession, session_id: str) -> MtdSession:
    s = await db.scalar(
        select(MtdSession)
        .where(MtdSession.id == session_id)
        .options(selectinload(MtdSession.cases))
    )
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MTD_SESSION_NOT_FOUND"},
        )
    return s


async def create_session(
    db: AsyncSession,
    body: MtdSessionCreate,
    caller_id: str,
) -> MtdSessionResponse:
    s = MtdSession(
        meeting_date=body.meeting_date,
        location=body.location,
        created_by=caller_id,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s, ["cases"])
    return MtdSessionResponse.model_validate(s)


async def list_sessions(
    db: AsyncSession,
    status_filter: str | None = None,
) -> list[MtdSessionResponse]:
    q = select(MtdSession).options(selectinload(MtdSession.cases))
    if status_filter:
        q = q.where(MtdSession.status == status_filter)
    q = q.order_by(MtdSession.meeting_date)
    rows = await db.scalars(q)
    return [MtdSessionResponse.model_validate(s) for s in rows.all()]


async def get_session(db: AsyncSession, session_id: str) -> MtdSessionResponse:
    s = await _get_session(db, session_id)
    return MtdSessionResponse.model_validate(s)


async def add_case(
    db: AsyncSession,
    session_id: str,
    body: MtdCaseCreate,
    caller_id: str,
) -> MtdSessionResponse:
    s = await _get_session(db, session_id)
    await get_patient(db, body.patient_mrn)

    existing = await db.scalar(
        select(MtdCase).where(
            MtdCase.mtd_session_id == session_id,
            MtdCase.patient_mrn == body.patient_mrn,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CASE_ALREADY_IN_SESSION"},
        )

    c = MtdCase(
        mtd_session_id=session_id,
        patient_mrn=body.patient_mrn,
        added_by=caller_id,
        reason=body.reason,
    )
    db.add(c)
    await db.flush()
    await db.refresh(s, ["cases"])
    return MtdSessionResponse.model_validate(s)


async def conclude_case(
    db: AsyncSession,
    session_id: str,
    mrn: str,
    body: MtdConclude,
    caller_id: str,
) -> MtdCaseResponse:
    s = await _get_session(db, session_id)

    # Verify caller is care_coordinator on this patient
    coordinator = await db.scalar(
        select(CareTeamMember).where(
            CareTeamMember.patient_mrn == mrn,
            CareTeamMember.user_id == caller_id,
            CareTeamMember.member_role == "care_coordinator",
            CareTeamMember.active.is_(True),
        )
    )
    if not coordinator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "MUST_BE_CARE_COORDINATOR"},
        )

    case = await db.scalar(
        select(MtdCase).where(
            MtdCase.mtd_session_id == session_id,
            MtdCase.patient_mrn == mrn,
        )
    )
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CASE_NOT_FOUND"},
        )

    if case.status == "pending":
        case.status = body.case_status
        case.conclusion_text = body.conclusion_text
        case.conclusion_by = caller_id
        case.conclusion_at = _now()
        await db.flush()

        await add_system_event(
            db,
            mrn=mrn,
            event_type="mtd_conclusion",
            title="MTD 結論已記錄",
            body_json={
                "conclusion_text": body.conclusion_text,
                "session_id": session_id,
                "meeting_date": s.meeting_date.isoformat(),
            },
        )

    return MtdCaseResponse.model_validate(case)


async def update_session_status(
    db: AsyncSession,
    session_id: str,
    body: MtdSessionStatusUpdate,
) -> MtdSessionResponse:
    s = await _get_session(db, session_id)
    s.status = body.status
    await db.flush()
    await db.refresh(s, ["cases"])
    return MtdSessionResponse.model_validate(s)
