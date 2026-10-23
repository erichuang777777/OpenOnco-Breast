"""HIS integration health status — GET /api/v1/admin/his-status."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import require_role
from hospital.db.models import Patient
from hospital.db.session import get_db

ADMIN_ROLES = ["kb_admin", "clinic_hcp", "tumor_board_hcp"]

router = APIRouter(prefix="/admin/his-status", tags=["admin"])


class HisPatientStatus(BaseModel):
    mrn: str
    his_patient_id: str
    his_synced_at: datetime | None
    status: str  # "ok" | "stale" | "never"


class HisHealthResponse(BaseModel):
    total_linked: int
    ok: int
    stale: int
    never_synced: int
    patients: list[HisPatientStatus]


@router.get("", response_model=HisHealthResponse)
async def his_health(
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> HisHealthResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    rows = await db.scalars(
        select(Patient).where(Patient.his_patient_id.is_not(None))
    )
    patients_list = []
    ok_count = stale_count = never_count = 0
    for p in rows.all():
        if p.his_synced_at is None:
            s = "never"
            never_count += 1
        elif p.his_synced_at < cutoff:
            s = "stale"
            stale_count += 1
        else:
            s = "ok"
            ok_count += 1
        patients_list.append(HisPatientStatus(
            mrn=p.mrn,
            his_patient_id=p.his_patient_id,
            his_synced_at=p.his_synced_at,
            status=s,
        ))
    return HisHealthResponse(
        total_linked=len(patients_list),
        ok=ok_count,
        stale=stale_count,
        never_synced=never_count,
        patients=patients_list,
    )
