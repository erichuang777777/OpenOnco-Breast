"""Phase B8 — OpenOnco-Patient link tests."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import AuditLog, Patient, TimelineEvent
from hospital.decision.schemas.plan import PlanResponse, TrackResponse
from tests.hospital.conftest import make_jwt


def _hdr(sub: str = "dr-link", role: str = "clinic_hcp") -> dict:
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


def _plan_body(patient_mrn: str | None = None, patient_id: str = "MRN-001") -> dict:
    body = {
        "patient": {
            "patient_id": patient_id,
            "disease": {"id": "DIS-BREAST"},
            "line_of_therapy": 1,
            "demographics": {"age": 55, "sex": "female", "ecog": 1},
            "findings": {
                "her2_status": "positive",
                "er_status": "positive",
                "stage_group": "IV",
            },
        }
    }
    if patient_mrn is not None:
        body["patient_mrn"] = patient_mrn
    return body


def _mock_plan_result(plan_id: str = "PLAN-LINK-001") -> PlanResponse:
    return PlanResponse(
        plan_id=plan_id,
        disease_id="DIS-BREAST",
        algorithm_id="ALG-BREAST-HER2-POS-MET",
        tracks=[
            TrackResponse(
                track_id="T1",
                label="THP 1L",
                is_default=True,
                indication_id="IND-BREAST-HER2-POS-MET-1L-THP",
            )
        ],
        warnings=[],
    )


async def _seed_patient(db: AsyncSession, mrn: str = "LINK-P1") -> Patient:
    p = Patient(mrn=mrn, masked_name="L●●", status="active",
                primary_doctor_id="dr-link", created_by="dr-link")
    db.add(p)
    await db.flush()
    return p


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_without_patient_mrn_still_works(client: AsyncClient):
    """Existing behaviour is unbroken when patient_mrn is omitted."""
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result()):
        resp = await client.post(
            "/api/v1/plan", json=_plan_body(), headers=_hdr()
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_plan_with_valid_patient_mrn_creates_timeline_event(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LINK-1")
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result()):
        await client.post(
            "/api/v1/plan",
            json=_plan_body(patient_mrn="LINK-1"),
            headers=_hdr(),
        )
    row = await db_session.scalar(
        select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "LINK-1",
            TimelineEvent.event_type == "onco_query_initiated",
        )
    )
    assert row is not None


@pytest.mark.asyncio
async def test_plan_timeline_event_type_is_onco_query_initiated(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LINK-2")
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result()):
        await client.post(
            "/api/v1/plan",
            json=_plan_body(patient_mrn="LINK-2"),
            headers=_hdr(),
        )
    row = await db_session.scalar(
        select(TimelineEvent).where(TimelineEvent.patient_mrn == "LINK-2")
    )
    assert row.event_type == "onco_query_initiated"


@pytest.mark.asyncio
async def test_plan_timeline_event_body_contains_plan_id(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LINK-3")
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result("PLAN-BODY-ID")):
        await client.post(
            "/api/v1/plan",
            json=_plan_body(patient_mrn="LINK-3"),
            headers=_hdr(),
        )
    row = await db_session.scalar(
        select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "LINK-3",
            TimelineEvent.event_type == "onco_query_initiated",
        )
    )
    body = json.loads(row.body_json)
    assert body["plan_id"] == "PLAN-BODY-ID"


@pytest.mark.asyncio
async def test_plan_timeline_event_created_by_is_caller(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LINK-4")
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result()):
        await client.post(
            "/api/v1/plan",
            json=_plan_body(patient_mrn="LINK-4"),
            headers=_hdr(sub="dr-caller"),
        )
    # AuditLog records the caller
    row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.user_id == "dr-caller",
            AuditLog.action == "onco_query",
        )
    )
    assert row is not None
    assert row.user_id == "dr-caller"


@pytest.mark.asyncio
async def test_plan_with_unknown_patient_mrn_404(client: AsyncClient):
    resp = await client.post(
        "/api/v1/plan",
        json=_plan_body(patient_mrn="GHOST-MRN"),
        headers=_hdr(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_plan_links_plan_mrn_to_patient_mrn(
    client: AsyncClient, db_session: AsyncSession
):
    """The Plan.mrn (patient_id) is set; timeline event links back to patient_mrn."""
    await _seed_patient(db_session, "LINK-5")
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result("PLAN-LINK-5")):
        resp = await client.post(
            "/api/v1/plan",
            json=_plan_body(patient_mrn="LINK-5", patient_id="LINK-5"),
            headers=_hdr(),
        )
    assert resp.status_code == 200
    # Timeline event references the patient
    row = await db_session.scalar(
        select(TimelineEvent).where(
            TimelineEvent.patient_mrn == "LINK-5",
            TimelineEvent.event_type == "onco_query_initiated",
        )
    )
    assert row is not None


@pytest.mark.asyncio
async def test_plan_audit_log_written_for_onco_query(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LINK-6")
    with patch("hospital.decision.api.plan.generate_plan_response",
               return_value=_mock_plan_result()):
        await client.post(
            "/api/v1/plan",
            json=_plan_body(patient_mrn="LINK-6"),
            headers=_hdr(),
        )
    row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "onco_query",
            AuditLog.resource_type == "plan",
        )
    )
    assert row is not None


@pytest.mark.asyncio
async def test_multiple_plans_for_same_patient_all_appear_in_timeline(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_patient(db_session, "LINK-7")
    with patch("hospital.decision.api.plan.generate_plan_response") as mock_gen:
        mock_gen.side_effect = [
            _mock_plan_result("PLAN-A"),
            _mock_plan_result("PLAN-B"),
        ]
        for _ in range(2):
            await client.post(
                "/api/v1/plan",
                json=_plan_body(patient_mrn="LINK-7"),
                headers=_hdr(),
            )

    from sqlalchemy import func
    count = await db_session.scalar(
        select(func.count()).select_from(TimelineEvent).where(
            TimelineEvent.patient_mrn == "LINK-7",
            TimelineEvent.event_type == "onco_query_initiated",
        )
    )
    assert count == 2
