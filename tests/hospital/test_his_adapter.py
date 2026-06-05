"""Phase B3 — HIS adapter interface tests."""

from __future__ import annotations

import json
import os

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import HisSyncEvent, Patient, TimelineEvent
from hospital.portals.his_adapter import HisAdapter, his_adapter
from hospital.portals.his_ingestion import ingest_his_event
from tests.hospital.conftest import make_jwt

HIS_SECRET = "test-his-secret-xyz"


def _hdr(sub="user-001", role="clinic_hcp"):
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


async def _seed(db: AsyncSession, mrn: str = "HIS-P1") -> Patient:
    p = Patient(mrn=mrn, masked_name="H●●", status="active",
                primary_doctor_id="u1", created_by="u1")
    db.add(p)
    await db.flush()
    return p


# ── adapter contract ──────────────────────────────────────────────────────────

def test_his_adapter_get_appointments_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        his_adapter.get_patient_appointments("ANY-MRN")


def test_his_adapter_get_medications_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        his_adapter.get_patient_medications("ANY-MRN")


def test_his_adapter_get_lab_results_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        his_adapter.get_lab_results("ANY-MRN")


def test_his_adapter_get_imaging_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        his_adapter.get_imaging_results("ANY-MRN")


# ── ingestion service ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingestion_appointment_creates_his_sync_event(db_session: AsyncSession):
    await _seed(db_session)
    event = await ingest_his_event(db_session, "HIS-P1", "appointment", {"date": "2026-07-01"})
    assert event.his_event_type == "appointment"
    assert event.patient_mrn == "HIS-P1"
    assert event.raw_mrn == "HIS-P1"


@pytest.mark.asyncio
async def test_ingestion_appointment_creates_timeline_event(db_session: AsyncSession):
    await _seed(db_session, "HIS-P2")
    await ingest_his_event(db_session, "HIS-P2", "appointment", {"date": "2026-07-15"})
    rows = list(await db_session.scalars(
        select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "HIS-P2",
            TimelineEvent.event_type == "his_sync",
        )
    ))
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_ingestion_unknown_mrn_creates_event_with_unmatched_flag(db_session: AsyncSession):
    event = await ingest_his_event(db_session, "UNKNOWN-MRN-999", "appointment", {"date": "2026-07-01"})
    assert event.patient_mrn is None
    assert event.raw_mrn == "UNKNOWN-MRN-999"
    payload = json.loads(event.payload_json)
    assert payload.get("_unmatched") is True


@pytest.mark.asyncio
async def test_ingestion_medication_event_stored(db_session: AsyncSession):
    await _seed(db_session, "HIS-P3")
    event = await ingest_his_event(db_session, "HIS-P3", "medication", {"drug": "Herceptin"})
    assert event.his_event_type == "medication"


@pytest.mark.asyncio
async def test_ingestion_lab_result_event_stored(db_session: AsyncSession):
    await _seed(db_session, "HIS-P4")
    event = await ingest_his_event(db_session, "HIS-P4", "lab_result", {"test": "CA15-3"})
    assert event.his_event_type == "lab_result"


@pytest.mark.asyncio
async def test_ingestion_imaging_event_stored(db_session: AsyncSession):
    await _seed(db_session, "HIS-P5")
    event = await ingest_his_event(db_session, "HIS-P5", "imaging", {"modality": "MRI"})
    assert event.his_event_type == "imaging"


# ── webhook ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_his_secret(monkeypatch):
    monkeypatch.setenv("HIS_WEBHOOK_SECRET", HIS_SECRET)
    from hospital import config as cfg
    cfg.get_settings.cache_clear()
    yield
    cfg.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_his_webhook_valid_secret_200(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, "HIS-W1")
    resp = await client.post(
        "/api/v1/his/ingest",
        json={"event_type": "appointment", "mrn": "HIS-W1", "payload": {"date": "2026-08-01"}},
        headers={"X-HIS-Secret": HIS_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_his_webhook_wrong_secret_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/his/ingest",
        json={"event_type": "appointment", "mrn": "ANY", "payload": {}},
        headers={"X-HIS-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_his_webhook_missing_secret_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/his/ingest",
        json={"event_type": "appointment", "mrn": "ANY", "payload": {}},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_his_webhook_malformed_json_422(client: AsyncClient):
    resp = await client.post(
        "/api/v1/his/ingest",
        content=b"not json",
        headers={"X-HIS-Secret": HIS_SECRET, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_his_webhook_unknown_event_type_422(client: AsyncClient):
    resp = await client.post(
        "/api/v1/his/ingest",
        json={"event_type": "vitals", "mrn": "ANY", "payload": {}},
        headers={"X-HIS-Secret": HIS_SECRET},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_his_webhook_stores_his_sync_event_in_db(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "HIS-W2")
    await client.post(
        "/api/v1/his/ingest",
        json={"event_type": "lab_result", "mrn": "HIS-W2", "payload": {"test": "HER2"}},
        headers={"X-HIS-Secret": HIS_SECRET},
    )
    rows = list(await db_session.scalars(
        select(HisSyncEvent).where(HisSyncEvent.raw_mrn == "HIS-W2")
    ))
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_his_webhook_creates_timeline_event_in_db(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "HIS-W3")
    await client.post(
        "/api/v1/his/ingest",
        json={"event_type": "medication", "mrn": "HIS-W3", "payload": {"drug": "Tamoxifen"}},
        headers={"X-HIS-Secret": HIS_SECRET},
    )
    rows = list(await db_session.scalars(
        select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "HIS-W3",
            TimelineEvent.event_type == "his_sync",
        )
    ))
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_his_webhook_idempotent_on_duplicate_payload(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "HIS-W4")
    body = {"event_type": "discharge", "mrn": "HIS-W4", "payload": {"date": "2026-06-10"}}
    r1 = await client.post("/api/v1/his/ingest", json=body, headers={"X-HIS-Secret": HIS_SECRET})
    r2 = await client.post("/api/v1/his/ingest", json=body, headers={"X-HIS-Secret": HIS_SECRET})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second call returns duplicate status
    assert r2.json()["status"] == "duplicate"


# ── patient list followup tab (moved from B1) ─────────────────────────────────

@pytest.mark.asyncio
async def test_patient_list_tab_followup_filters_correctly(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session, "HIS-FU1")
    # Seed a HIS appointment sync event for this patient
    await ingest_his_event(
        db_session, "HIS-FU1", "appointment",
        {"date": "2026-07-15", "type": "followup"},
        sync_source="his_webhook",
    )
    # Create another patient without appointments
    db_session.add(Patient(mrn="HIS-FU2", masked_name="N●●", status="active",
                           primary_doctor_id="u1", created_by="u1"))
    await db_session.flush()

    # followup tab: patients with recent his_sync events of type appointment
    resp = await client.get("/api/v1/patients?tab=followup", headers=_hdr("u1"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "HIS-FU1" in mrns
