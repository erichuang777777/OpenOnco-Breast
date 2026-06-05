"""Consultation service — Phase B5."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hospital.db.models import Consultation, ConsultationMessage, User
from hospital.decision.schemas.consultation import (
    ConsultationCreate,
    ConsultationMessageCreate,
    ConsultationMessageResponse,
    ConsultationResponse,
)
from hospital.decision.services.patient_service import get_patient
from hospital.decision.services.timeline_service import add_system_event


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_consultation(
    db: AsyncSession, consultation_id: str
) -> Consultation:
    c = await db.scalar(
        select(Consultation)
        .where(Consultation.id == consultation_id)
        .options(selectinload(Consultation.messages))
    )
    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CONSULTATION_NOT_FOUND"},
        )
    return c


async def _require_participant(c: Consultation, user_id: str) -> None:
    if user_id not in (c.from_user_id, c.to_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "NOT_CONSULTATION_PARTICIPANT"},
        )


async def create_consultation(
    db: AsyncSession,
    mrn: str,
    body: ConsultationCreate,
    caller_id: str,
) -> ConsultationResponse:
    await get_patient(db, mrn)

    # Verify recipient exists
    to_user = await db.scalar(
        select(User).where(User.user_id == body.to_user_id)
    )
    if not to_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "USER_NOT_FOUND"},
        )

    c = Consultation(
        patient_mrn=mrn,
        from_user_id=caller_id,
        to_user_id=body.to_user_id,
        subject=body.subject,
    )
    db.add(c)
    await db.flush()
    await db.refresh(c, ["messages"])
    return ConsultationResponse.model_validate(c)


async def list_consultations_for_patient(
    db: AsyncSession, mrn: str
) -> list[ConsultationResponse]:
    await get_patient(db, mrn)
    rows = await db.scalars(
        select(Consultation)
        .where(Consultation.patient_mrn == mrn)
        .options(selectinload(Consultation.messages))
        .order_by(Consultation.created_at.desc())
    )
    return [ConsultationResponse.model_validate(c) for c in rows.all()]


async def list_my_consultations(
    db: AsyncSession,
    user_id: str,
    role: str = "all",
) -> list[ConsultationResponse]:
    q = select(Consultation).options(selectinload(Consultation.messages))
    if role == "sent":
        q = q.where(Consultation.from_user_id == user_id)
    elif role == "received":
        q = q.where(Consultation.to_user_id == user_id)
    else:
        q = q.where(
            or_(
                Consultation.from_user_id == user_id,
                Consultation.to_user_id == user_id,
            )
        )
    q = q.order_by(Consultation.updated_at.desc())
    rows = await db.scalars(q)
    return [ConsultationResponse.model_validate(c) for c in rows.all()]


async def add_message(
    db: AsyncSession,
    consultation_id: str,
    body: ConsultationMessageCreate,
    caller_id: str,
) -> ConsultationResponse:
    c = await _get_consultation(db, consultation_id)
    await _require_participant(c, caller_id)

    if c.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CONSULTATION_CLOSED"},
        )

    msg = ConsultationMessage(
        consultation_id=c.id,
        sender_id=caller_id,
        body=body.body,
    )
    db.add(msg)
    if c.status == "open":
        c.status = "replied"
    c.updated_at = _now()
    await db.flush()

    await add_system_event(
        db,
        mrn=c.patient_mrn,
        event_type="consultation_reply",
        title=f"諮詢回覆 — {c.subject[:40]}",
        body_json={"sender_id": caller_id},
    )

    await db.refresh(c, ["messages"])
    return ConsultationResponse.model_validate(c)


async def close_consultation(
    db: AsyncSession,
    consultation_id: str,
    caller_id: str,
) -> ConsultationResponse:
    c = await _get_consultation(db, consultation_id)

    if c.from_user_id != caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "ONLY_SENDER_CAN_CLOSE"},
        )

    if c.status != "closed":
        c.status = "closed"
        c.updated_at = _now()
        await db.flush()

    await db.refresh(c, ["messages"])
    return ConsultationResponse.model_validate(c)
