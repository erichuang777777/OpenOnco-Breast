"""Reminder service — CRUD + rule evaluation (Phase B4)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from hospital.db.models import Patient, Reminder, User
from hospital.decision.services.patient_service import get_patient
from hospital.decision.services.reminder_rules import ALL_RULES


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReminderCreate(BaseModel):
    title: str
    detail: str | None = None
    due_date: datetime
    reminder_type: str = "custom"

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v

    @field_validator("due_date")
    @classmethod
    def due_date_in_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("due_date must be in the future")
        return v


class ReminderResponse(BaseModel):
    id: str
    patient_mrn: str
    reminder_type: str
    urgency: str
    title: str
    detail: str | None
    due_date: datetime
    status: str
    triggered_by: str
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_reminders(
    db: AsyncSession,
    mrn: str,
    reminder_status: str | None = None,
) -> list[ReminderResponse]:
    await get_patient(db, mrn)
    q = select(Reminder).where(Reminder.patient_mrn == mrn)
    if reminder_status:
        q = q.where(Reminder.status == reminder_status)
    q = q.order_by(Reminder.due_date)
    rows = await db.scalars(q)
    return [ReminderResponse.model_validate(r) for r in rows.all()]


async def acknowledge_reminder(
    db: AsyncSession,
    mrn: str,
    reminder_id: str,
    user_id: str,
) -> ReminderResponse:
    await get_patient(db, mrn)
    r = await db.scalar(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.patient_mrn == mrn)
    )
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REMINDER_NOT_FOUND"},
        )
    if r.status == "active":
        r.status = "acknowledged"
        r.acknowledged_by = user_id
        r.acknowledged_at = _now()
        await db.flush()
    return ReminderResponse.model_validate(r)


async def create_custom_reminder(
    db: AsyncSession,
    mrn: str,
    body: ReminderCreate,
    user_id: str,
) -> ReminderResponse:
    await get_patient(db, mrn)
    r = Reminder(
        patient_mrn=mrn,
        reminder_type=body.reminder_type,
        urgency="normal",
        title=body.title,
        detail=body.detail,
        due_date=body.due_date,
        triggered_by=f"manual:{user_id}",
    )
    db.add(r)
    await db.flush()
    return ReminderResponse.model_validate(r)


# ── Rule evaluation ───────────────────────────────────────────────────────────

async def evaluate_patient(db: AsyncSession, mrn: str) -> list[str]:
    """Run all rules for one patient. Returns list of rule IDs that fired."""
    fired = []
    for rule_fn in ALL_RULES:
        try:
            result = await rule_fn(db, mrn)
            if result:
                fired.append(rule_fn.__name__)
        except Exception:
            pass
    return fired


async def evaluate_all_patients(db: AsyncSession) -> dict[str, list[str]]:
    """Run all rules for every active patient. Returns mrn → fired rules."""
    mrns = await db.scalars(select(Patient.mrn).where(Patient.status == "active"))
    results = {}
    for mrn in mrns.all():
        results[mrn] = await evaluate_patient(db, mrn)
    return results


async def notify_care_team_line(
    db: AsyncSession,
    mrn: str,
    reminder: Reminder,
) -> None:
    """
    Send LINE Notify message to all care-team members who have registered a token,
    but only for high/critical urgency reminders when LINE_NOTIFY_ENABLED=True.
    """
    from hospital.config import get_settings
    if not get_settings().LINE_NOTIFY_ENABLED:
        return
    if reminder.urgency not in ("high", "critical"):
        return

    from hospital.db.models import CareTeamMember
    from hospital.services.line_notify import format_reminder_message, send_line_notify

    members = await db.scalars(
        select(CareTeamMember).where(CareTeamMember.patient_mrn == mrn)
    )
    user_ids = [m.user_id for m in members.all()]
    if not user_ids:
        return

    users = await db.scalars(
        select(User).where(User.user_id.in_(user_ids), User.line_notify_token.is_not(None))
    )
    message = format_reminder_message(mrn, reminder.title, reminder.urgency)
    for u in users.all():
        if u.line_notify_token:
            await send_line_notify(u.line_notify_token, message)
