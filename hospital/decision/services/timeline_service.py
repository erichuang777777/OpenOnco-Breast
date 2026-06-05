"""Timeline event service — B2 business logic.

HTTP layer: doctor_note / coordinator_note only.
Service layer: all types (his_sync, alert, mtd_conclusion, etc.) via add_system_event().
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import TimelineEvent
from hospital.decision.schemas.timeline import TimelineEventCreate, TimelineEventResponse
from hospital.decision.services.patient_service import get_patient


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def list_events(
    db: AsyncSession,
    mrn: str,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TimelineEventResponse]:
    await get_patient(db, mrn)  # 404 if unknown
    q = select(TimelineEvent).where(TimelineEvent.patient_mrn == mrn)
    if event_type:
        q = q.where(TimelineEvent.event_type == event_type)
    q = q.order_by(TimelineEvent.event_time.desc()).limit(limit).offset(offset)
    rows = await db.scalars(q)
    return [TimelineEventResponse.model_validate(r) for r in rows.all()]


async def add_manual_event(
    db: AsyncSession,
    mrn: str,
    body: TimelineEventCreate,
    user_id: str,
) -> TimelineEventResponse:
    await get_patient(db, mrn)  # 404 if unknown
    event = TimelineEvent(
        patient_mrn=mrn,
        event_type=body.event_type,
        event_time=body.event_time or _now(),
        source="manual",
        title=body.title,
        body_json=json.dumps(body.body_json) if body.body_json else None,
        created_by=user_id,
    )
    db.add(event)
    await db.flush()
    return TimelineEventResponse.model_validate(event)


async def add_system_event(
    db: AsyncSession,
    mrn: str,
    event_type: str,
    title: str,
    source: str = "system_rule",
    body_json: dict | None = None,
    event_time: datetime | None = None,
) -> TimelineEvent:
    """Service-layer only — writes system events (his_sync, alert, mtd_conclusion, etc.)."""
    event = TimelineEvent(
        patient_mrn=mrn,
        event_type=event_type,
        event_time=event_time or _now(),
        source=source,
        title=title,
        body_json=json.dumps(body_json) if body_json else None,
        created_by=None,
    )
    db.add(event)
    await db.flush()
    return event
