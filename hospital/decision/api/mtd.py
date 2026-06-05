"""MTD API — Phase B6."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.decision.schemas.mtd import (
    MtdCaseCreate,
    MtdCaseResponse,
    MtdConclude,
    MtdSessionCreate,
    MtdSessionResponse,
    MtdSessionStatusUpdate,
)
from hospital.decision.services.mtd_service import (
    add_case,
    conclude_case,
    create_session,
    get_session,
    list_sessions,
    update_session_status,
)

router = APIRouter(tags=["mtd"])

BOARD_ROLES = {"tumor_board_hcp", "kb_admin"}


@router.get("/mtd/sessions", response_model=list[MtdSessionResponse])
async def get_sessions(
    status: str | None = None,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[MtdSessionResponse]:
    return await list_sessions(db, status_filter=status)


@router.post(
    "/mtd/sessions",
    response_model=MtdSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_session(
    body: MtdSessionCreate,
    user: dict = Depends(require_role(BOARD_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MtdSessionResponse:
    return await create_session(db, body, user["sub"])


@router.get("/mtd/sessions/{session_id}", response_model=MtdSessionResponse)
async def get_session_detail(
    session_id: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MtdSessionResponse:
    return await get_session(db, session_id)


@router.post(
    "/mtd/sessions/{session_id}/cases",
    response_model=MtdSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_case(
    session_id: str,
    body: MtdCaseCreate,
    user: dict = Depends(require_role(BOARD_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MtdSessionResponse:
    return await add_case(db, session_id, body, user["sub"])


@router.patch(
    "/mtd/sessions/{session_id}/cases/{mrn}/conclude",
    response_model=MtdCaseResponse,
)
async def patch_conclude(
    session_id: str,
    mrn: str,
    body: MtdConclude,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MtdCaseResponse:
    return await conclude_case(db, session_id, mrn, body, user["sub"])


@router.patch("/mtd/sessions/{session_id}", response_model=MtdSessionResponse)
async def patch_session_status(
    session_id: str,
    body: MtdSessionStatusUpdate,
    user: dict = Depends(require_role(BOARD_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MtdSessionResponse:
    return await update_session_status(db, session_id, body)
