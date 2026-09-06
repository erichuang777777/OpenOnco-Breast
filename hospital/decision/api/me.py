"""User self-service endpoints — /api/v1/me/

Allows authenticated users to manage their own profile settings
(e.g. LINE Notify token) without admin privileges.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, ADMIN_ROLES, require_role

ALL_AUTHENTICATED = HCP_ROLES + ADMIN_ROLES + ["auditor"]
from hospital.db.models import User
from hospital.db.session import get_db

router = APIRouter(prefix="/me", tags=["me"])


class LineNotifyTokenRequest(BaseModel):
    token: str | None  # None = unregister / clear the token


class LineNotifyStatusResponse(BaseModel):
    registered: bool


@router.put("/line-notify-token", response_model=LineNotifyStatusResponse)
async def set_line_notify_token(
    body: LineNotifyTokenRequest,
    user: dict = Depends(require_role(ALL_AUTHENTICATED)),
    db: AsyncSession = Depends(get_db),
) -> LineNotifyStatusResponse:
    """Save or clear the caller's LINE Notify personal access token."""
    row = await db.scalar(select(User).where(User.user_id == user["sub"]))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    token = body.token.strip() if body.token else None
    row.line_notify_token = token or None
    await db.flush()
    return LineNotifyStatusResponse(registered=row.line_notify_token is not None)


@router.get("/line-notify-token", response_model=LineNotifyStatusResponse)
async def get_line_notify_status(
    user: dict = Depends(require_role(ALL_AUTHENTICATED)),
    db: AsyncSession = Depends(get_db),
) -> LineNotifyStatusResponse:
    """Check whether the caller has a LINE Notify token registered."""
    row = await db.scalar(select(User).where(User.user_id == user["sub"]))
    return LineNotifyStatusResponse(registered=bool(row and row.line_notify_token))
