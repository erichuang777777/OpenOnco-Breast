"""Reminders API — Phase B4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import ADMIN_ROLES, HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.decision.services.reminder_service import (
    ReminderCreate,
    ReminderResponse,
    acknowledge_reminder,
    create_custom_reminder,
    evaluate_all_patients,
    list_reminders,
)

router = APIRouter(tags=["reminders"])
admin_router = APIRouter(tags=["admin-reminders"])


@router.get("/patients/{mrn}/reminders", response_model=list[ReminderResponse])
async def get_reminders(
    mrn: str,
    reminder_status: str | None = None,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[ReminderResponse]:
    return await list_reminders(db, mrn, reminder_status=reminder_status)


@router.patch(
    "/patients/{mrn}/reminders/{reminder_id}/acknowledge",
    response_model=ReminderResponse,
)
async def ack_reminder(
    mrn: str,
    reminder_id: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ReminderResponse:
    return await acknowledge_reminder(db, mrn, reminder_id, user["sub"])


@router.post(
    "/patients/{mrn}/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reminder(
    mrn: str,
    body: ReminderCreate,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ReminderResponse:
    return await create_custom_reminder(db, mrn, body, user["sub"])


@admin_router.post("/admin/reminders/evaluate", status_code=status.HTTP_200_OK)
async def force_evaluate(
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    results = await evaluate_all_patients(db)
    return {"evaluated": len(results), "fired": {k: v for k, v in results.items() if v}}
