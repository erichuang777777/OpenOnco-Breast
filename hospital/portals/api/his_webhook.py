"""HIS inbound webhook — POST /api/v1/his/ingest (Phase B3).

Auth: X-HIS-Secret header (HMAC shared secret configured in settings).
Idempotency: de-dup on (raw_mrn, his_event_type, payload hash).
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.config import get_settings
from hospital.db.models import HisSyncEvent
from hospital.db.session import get_db
from hospital.portals.his_ingestion import ingest_his_event

_limiter = Limiter(key_func=get_remote_address)

VALID_HIS_EVENT_TYPES = {"appointment", "medication", "lab_result", "imaging", "discharge"}

router = APIRouter(prefix="/his", tags=["his"])


class HisIngestBody(BaseModel):
    event_type: str
    mrn: str
    payload: dict = {}


@router.post("/ingest", status_code=status.HTTP_200_OK)
@_limiter.limit(get_settings().RATE_LIMIT_HIS_WEBHOOK)
async def his_ingest(
    request: Request,
    body: HisIngestBody,
    x_his_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.HIS_WEBHOOK_SECRET or x_his_secret != settings.HIS_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_HIS_SECRET", "message": "Missing or wrong X-HIS-Secret."},
        )
    if body.event_type not in VALID_HIS_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "UNKNOWN_EVENT_TYPE", "message": f"Unknown event_type: {body.event_type!r}"},
        )

    # Idempotency: hash of (mrn + event_type + sorted payload)
    payload_hash = hashlib.sha256(
        json.dumps({"mrn": body.mrn, "type": body.event_type, "payload": body.payload},
                   sort_keys=True).encode()
    ).hexdigest()

    existing = await db.scalar(
        select(HisSyncEvent).where(
            HisSyncEvent.raw_mrn == body.mrn,
            HisSyncEvent.his_event_type == body.event_type,
            HisSyncEvent.payload_json.contains(payload_hash[:16]),  # fast pre-filter
        )
    )
    # Full idempotency: check payload_json contains the hash marker
    dupes = await db.scalars(
        select(HisSyncEvent).where(
            HisSyncEvent.raw_mrn == body.mrn,
            HisSyncEvent.his_event_type == body.event_type,
        )
    )
    for d in dupes.all():
        try:
            stored = json.loads(d.payload_json)
            if stored.get("_idempotency_key") == payload_hash:
                return {"status": "duplicate", "id": d.id}
        except Exception:
            pass

    body.payload["_idempotency_key"] = payload_hash
    event = await ingest_his_event(db, body.mrn, body.event_type, body.payload)
    return {"status": "ok", "id": event.id}
