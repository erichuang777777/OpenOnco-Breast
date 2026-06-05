"""Admin audit log endpoint — GET /api/v1/admin/audit."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import require_role
from hospital.db.models import AuditLog
from hospital.db.session import get_db

# Both kb_admin and auditor may read audit logs; only kb_admin may mutate users.
AUDIT_VIEWER_ROLES = ["kb_admin", "auditor"]

router = APIRouter(prefix="/admin/audit", tags=["admin"])


class AuditEntryResponse(BaseModel):
    id: str
    ts: datetime
    user_id: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    diff_summary: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditEntryResponse])
async def list_audit_log(
    user_id_filter: Optional[str] = Query(None, alias="user_id"),
    limit: int = Query(200, le=1000),
    user: dict = Depends(require_role(AUDIT_VIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEntryResponse]:
    stmt = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)
    if user_id_filter:
        stmt = stmt.where(AuditLog.user_id == user_id_filter)
    rows = list(await db.scalars(stmt))
    return [AuditEntryResponse.model_validate(r) for r in rows]
