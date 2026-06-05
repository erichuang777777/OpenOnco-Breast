"""Timeline Events API — /api/v1/patients/{mrn}/timeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.decision.schemas.timeline import TimelineEventCreate, TimelineEventResponse
from hospital.decision.services import timeline_service

router = APIRouter(prefix="/patients/{mrn}/timeline", tags=["timeline"])


@router.get("", response_model=list[TimelineEventResponse])
async def list_timeline(
    mrn: str,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEventResponse]:
    return await timeline_service.list_events(db, mrn, event_type=type, limit=limit, offset=offset)


@router.post("", response_model=TimelineEventResponse, status_code=status.HTTP_201_CREATED)
async def add_timeline_event(
    mrn: str,
    body: TimelineEventCreate,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> TimelineEventResponse:
    return await timeline_service.add_manual_event(db, mrn, body, user["sub"])
