"""Phase B1 — Patient Registry API tests.

Gate: pytest tests/hospital/test_models_b0.py tests/hospital/test_patient_api.py
      --asyncio-mode=auto -x -q
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import (
    AuditLog,
    CareTeamMember,
    Consultation,
    MtdCase,
    MtdSession,
    Patient,
    Reminder,
)
from hospital.services import audit_service
from tests.hospital.conftest import make_jwt

from sqlalchemy import select
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _hdr(sub="user-001", role="clinic_hcp"):
    return {"Authorization": f"Bearer {make_jwt(sub=sub, role=role)}"}


# ── list ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_list_returns_only_my_patients(
    client: AsyncClient, db_session: AsyncSession
):
    # user-001 owns patient A, user-002 owns patient B
    db_session.add_all([
        Patient(mrn="LIST-A", masked_name="A", status="active", primary_doctor_id="user-001", created_by="user-001"),
        Patient(mrn="LIST-B", masked_name="B", status="active", primary_doctor_id="user-002", created_by="user-002"),
    ])
    await db_session.flush()
    resp = await client.get("/api/v1/patients", headers=_hdr("user-001"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "LIST-A" in mrns
    assert "LIST-B" not in mrns


@pytest.mark.asyncio
async def test_patient_list_tab_consulted_returns_inbound(
    client: AsyncClient, db_session: AsyncSession
):
    db_session.add(Patient(mrn="CONS-P1", masked_name="X", status="active",
                           primary_doctor_id="user-001", created_by="user-001"))
    await db_session.flush()
    db_session.add(Consultation(patient_mrn="CONS-P1", from_user_id="user-001",
                                to_user_id="user-002", subject="Q", status="open"))
    await db_session.flush()
    # user-002 queries consulted tab
    resp = await client.get("/api/v1/patients?tab=consulted", headers=_hdr("user-002"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "CONS-P1" in mrns


@pytest.mark.asyncio
async def test_patient_list_tab_mtd_returns_scheduled(
    client: AsyncClient, db_session: AsyncSession
):
    db_session.add(Patient(mrn="MTD-P1", masked_name="Y", status="active",
                           primary_doctor_id="user-001", created_by="user-001"))
    await db_session.flush()
    mtd = MtdSession(meeting_date=_now(), created_by="user-001", status="scheduled")
    db_session.add(mtd)
    await db_session.flush()
    db_session.add(MtdCase(mtd_session_id=mtd.id, patient_mrn="MTD-P1", added_by="user-001"))
    await db_session.flush()
    resp = await client.get("/api/v1/patients?tab=mtd", headers=_hdr("user-002"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "MTD-P1" in mrns


@pytest.mark.asyncio
async def test_patient_list_tab_alerts_returns_urgent_reminders(
    client: AsyncClient, db_session: AsyncSession
):
    db_session.add(Patient(mrn="ALRT-P1", masked_name="Z", status="active",
                           primary_doctor_id="user-001", created_by="user-001"))
    await db_session.flush()
    db_session.add(Reminder(
        patient_mrn="ALRT-P1", reminder_type="custom", urgency="high",
        title="urgent", due_date=_now(), triggered_by="test", status="active",
    ))
    await db_session.flush()
    resp = await client.get("/api/v1/patients?tab=alerts", headers=_hdr("user-001"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "ALRT-P1" in mrns


@pytest.mark.asyncio
async def test_patient_list_empty_for_new_user(client: AsyncClient):
    resp = await client.get("/api/v1/patients", headers=_hdr("user-new-999"))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_patient_list_includes_care_team_members(
    client: AsyncClient, db_session: AsyncSession
):
    db_session.add(Patient(mrn="TEAM-P1", masked_name="T", status="active",
                           primary_doctor_id="user-001", created_by="user-001"))
    await db_session.flush()
    db_session.add(CareTeamMember(patient_mrn="TEAM-P1", user_id="coord-001",
                                  member_role="care_coordinator", assigned_by="user-001"))
    await db_session.flush()
    resp = await client.get("/api/v1/patients", headers=_hdr("coord-001"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "TEAM-P1" in mrns


@pytest.mark.asyncio
async def test_patient_list_excludes_unrelated_doctor(
    client: AsyncClient, db_session: AsyncSession
):
    db_session.add(Patient(mrn="EXCL-P1", masked_name="E", status="active",
                           primary_doctor_id="user-001", created_by="user-001"))
    await db_session.flush()
    resp = await client.get("/api/v1/patients", headers=_hdr("user-unrelated"))
    assert resp.status_code == 200
    mrns = [p["mrn"] for p in resp.json()]
    assert "EXCL-P1" not in mrns


@pytest.mark.asyncio
async def test_patient_list_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/patients")
    assert resp.status_code == 401


# ── create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_create_success_201(client: AsyncClient):
    resp = await client.post(
        "/api/v1/patients",
        json={"mrn": "NEW-001", "masked_name": "李●●", "sex": "M", "dob_year": 1960},
        headers=_hdr(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["mrn"] == "NEW-001"
    assert data["masked_name"] == "李●●"


@pytest.mark.asyncio
async def test_patient_create_sets_primary_doctor(client: AsyncClient):
    resp = await client.post(
        "/api/v1/patients",
        json={"mrn": "NEW-002", "masked_name": "陳●●"},
        headers=_hdr("dr-owner"),
    )
    assert resp.status_code == 201
    assert resp.json()["primary_doctor_id"] == "dr-owner"


@pytest.mark.asyncio
async def test_patient_create_duplicate_mrn_409(client: AsyncClient):
    payload = {"mrn": "DUP-001", "masked_name": "趙●●"}
    await client.post("/api/v1/patients", json=payload, headers=_hdr())
    resp = await client.post("/api/v1/patients", json=payload, headers=_hdr())
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patient_create_pending_role_403(client: AsyncClient):
    resp = await client.post(
        "/api/v1/patients",
        json={"mrn": "PEND-001", "masked_name": "待●●"},
        headers={"Authorization": f"Bearer {make_jwt(role='pending')}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patient_create_invalid_status_422(client: AsyncClient):
    resp = await client.post(
        "/api/v1/patients",
        json={"mrn": "BAD-001", "masked_name": "錯●●", "status": "unknown"},
        headers=_hdr(),
    )
    assert resp.status_code == 422


# ── get single ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_get_own_patient_200(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.get(f"/api/v1/patients/{sample_patient.mrn}", headers=_hdr("user-001"))
    assert resp.status_code == 200
    assert resp.json()["mrn"] == sample_patient.mrn


@pytest.mark.asyncio
async def test_patient_get_cross_doctor_allowed_200(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.get(f"/api/v1/patients/{sample_patient.mrn}", headers=_hdr("user-other"))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_patient_get_cross_doctor_writes_audit_log(
    client: AsyncClient, sample_patient: Patient, db_session: AsyncSession
):
    await client.get(f"/api/v1/patients/{sample_patient.mrn}", headers=_hdr("user-stranger"))
    logs = list(await db_session.scalars(
        select(AuditLog).where(
            AuditLog.user_id == "user-stranger",
            AuditLog.action == audit_service.PATIENT_CROSS_ACCESS,
        )
    ))
    assert len(logs) >= 1


@pytest.mark.asyncio
async def test_patient_get_care_team_member_no_audit_log(
    client: AsyncClient, sample_patient: Patient,
    sample_care_team: list, db_session: AsyncSession
):
    # coord-001 is on care team — should NOT write cross_access log
    await client.get(f"/api/v1/patients/{sample_patient.mrn}", headers=_hdr("coord-001"))
    logs = list(await db_session.scalars(
        select(AuditLog).where(
            AuditLog.user_id == "coord-001",
            AuditLog.action == audit_service.PATIENT_CROSS_ACCESS,
        )
    ))
    assert len(logs) == 0


@pytest.mark.asyncio
async def test_patient_get_unknown_mrn_404(client: AsyncClient):
    resp = await client.get("/api/v1/patients/GHOST-MRN", headers=_hdr())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patient_get_requires_auth(client: AsyncClient, sample_patient: Patient):
    resp = await client.get(f"/api/v1/patients/{sample_patient.mrn}")
    assert resp.status_code == 401


# ── patch ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_patch_disease_summary(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.patch(
        f"/api/v1/patients/{sample_patient.mrn}",
        json={"disease_summary": "乳癌 HER2+ · 第三期"},
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 200
    assert resp.json()["disease_summary"] == "乳癌 HER2+ · 第三期"


@pytest.mark.asyncio
async def test_patient_patch_status_to_discharged(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.patch(
        f"/api/v1/patients/{sample_patient.mrn}",
        json={"status": "discharged"},
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "discharged"


@pytest.mark.asyncio
async def test_patient_patch_unknown_field_ignored(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.patch(
        f"/api/v1/patients/{sample_patient.mrn}",
        json={"disease_summary": "updated", "totally_unknown_field": "ignored"},
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_patient_patch_invalid_status_422(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.patch(
        f"/api/v1/patients/{sample_patient.mrn}",
        json={"status": "zombie"},
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patient_patch_non_team_member_allowed(
    client: AsyncClient, sample_patient: Patient, db_session: AsyncSession
):
    # unrelated HCP can still patch (EMR-parity) — writes cross_access audit
    resp = await client.patch(
        f"/api/v1/patients/{sample_patient.mrn}",
        json={"disease_summary": "cross edit"},
        headers=_hdr("user-outsider"),
    )
    assert resp.status_code == 200
    logs = list(await db_session.scalars(
        select(AuditLog).where(
            AuditLog.user_id == "user-outsider",
            AuditLog.action == audit_service.PATIENT_CROSS_ACCESS,
        )
    ))
    assert len(logs) >= 1


# ── care team ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_care_team_list_returns_members(
    client: AsyncClient, sample_patient: Patient, sample_care_team: list
):
    resp = await client.get(
        f"/api/v1/patients/{sample_patient.mrn}/care-team", headers=_hdr("user-001")
    )
    assert resp.status_code == 200
    user_ids = [m["user_id"] for m in resp.json()]
    assert "user-001" in user_ids
    assert "coord-001" in user_ids


@pytest.mark.asyncio
async def test_care_team_add_member_201(
    client: AsyncClient, sample_patient: Patient, sample_care_team: list
):
    resp = await client.post(
        f"/api/v1/patients/{sample_patient.mrn}/care-team",
        json={"user_id": "consult-dr", "member_role": "consultant", "specialty": "Radiology"},
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == "consult-dr"


@pytest.mark.asyncio
async def test_care_team_add_duplicate_409(
    client: AsyncClient, sample_patient: Patient, sample_care_team: list
):
    # coord-001 is already on team (from sample_care_team)
    resp = await client.post(
        f"/api/v1/patients/{sample_patient.mrn}/care-team",
        json={"user_id": "coord-001", "member_role": "consultant"},
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_care_team_add_by_non_primary_403(
    client: AsyncClient, sample_patient: Patient
):
    # user-other is not primary_doctor
    resp = await client.post(
        f"/api/v1/patients/{sample_patient.mrn}/care-team",
        json={"user_id": "new-dr", "member_role": "consultant"},
        headers=_hdr("user-other"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_care_team_remove_success_204(
    client: AsyncClient, sample_patient: Patient, sample_care_team: list
):
    resp = await client.delete(
        f"/api/v1/patients/{sample_patient.mrn}/care-team/coord-001",
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_care_team_remove_self_allowed(
    client: AsyncClient, sample_patient: Patient, sample_care_team: list
):
    # primary doctor can remove themselves
    resp = await client.delete(
        f"/api/v1/patients/{sample_patient.mrn}/care-team/user-001",
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_care_team_remove_nonexistent_404(
    client: AsyncClient, sample_patient: Patient
):
    resp = await client.delete(
        f"/api/v1/patients/{sample_patient.mrn}/care-team/ghost-user",
        headers=_hdr("user-001"),
    )
    assert resp.status_code == 404
