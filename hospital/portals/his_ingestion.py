"""HIS ingestion service — Phase B3.

Parses inbound HIS event payloads into:
  1. HisSyncEvent row (raw audit trail; patient_mrn=NULL if MRN unmatched)
  2. TimelineEvent row (human-readable log, only if patient exists)

raw_mrn always stores the MRN string from the payload for traceability.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import HisSyncEvent, Patient
from hospital.decision.services.timeline_service import add_system_event

_TYPE_TO_TITLE = {
    "appointment": "HIS: 門診/住院預約",
    "medication": "HIS: 用藥記錄更新",
    "lab_result": "HIS: 檢驗結果",
    "imaging": "HIS: 影像報告",
    "discharge": "HIS: 出院記錄",
}


async def ingest_his_event(
    db: AsyncSession,
    mrn: str,
    his_event_type: str,
    payload: dict,
    sync_source: str = "his_webhook",
) -> HisSyncEvent:
    """Store HisSyncEvent + optional TimelineEvent.

    Unknown MRNs: stored with patient_mrn=NULL and _unmatched flag in payload.
    """
    patient_exists = bool(await db.scalar(select(Patient).where(Patient.mrn == mrn)))

    stored_payload = dict(payload)
    if not patient_exists:
        stored_payload["_unmatched"] = True

    event = HisSyncEvent(
        patient_mrn=mrn if patient_exists else None,
        raw_mrn=mrn,
        his_event_type=his_event_type,
        payload_json=json.dumps(stored_payload),
        sync_source=sync_source,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()

    if patient_exists:
        title = _TYPE_TO_TITLE.get(his_event_type, f"HIS: {his_event_type}")
        await add_system_event(
            db, mrn, "his_sync", title,
            source="his_sync",
            body_json=payload,
        )

    return event
