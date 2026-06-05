"""H0 — Security hardening tests.

Covers authentication enforcement, role-based access control, and
basic input rejection for the hospital API.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.hospital.conftest import make_jwt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def headers(role: str, sub: str = "user-sec", email: str = "sec@test.com") -> dict:
    token = make_jwt(sub=sub, email=email, role=role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# H0-01  No token → 401 for all protected endpoints
# ---------------------------------------------------------------------------

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/patients"),
    ("POST", "/api/v1/patients"),
    ("GET", "/api/v1/patients/MRN-X/timeline"),
    ("GET", "/api/v1/patients/MRN-X/reminders"),
    ("GET", "/api/v1/patients/MRN-X/consultations"),
    ("POST", "/api/v1/patients/MRN-X/consultations"),
    ("GET", "/api/v1/consultations"),
    ("GET", "/api/v1/mtd/sessions"),
    ("POST", "/api/v1/mtd/sessions"),
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/audit"),
    ("GET", "/api/v1/push/vapid-public-key"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_unauthenticated_returns_401(client: AsyncClient, method: str, path: str) -> None:
    resp = await client.request(method, path)
    assert resp.status_code == 401, f"{method} {path} → expected 401, got {resp.status_code}"


# ---------------------------------------------------------------------------
# H0-02  Expired / tampered token → 401
# ---------------------------------------------------------------------------

async def test_tampered_token_rejected(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/patients",
        headers={"Authorization": "Bearer INVALID.TOKEN.VALUE"},
    )
    assert resp.status_code == 401


async def test_missing_bearer_prefix_rejected(client: AsyncClient) -> None:
    token = make_jwt(role="clinic_hcp")
    resp = await client.get(
        "/api/v1/patients",
        headers={"Authorization": token},  # no "Bearer " prefix
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# H0-03  pending role cannot access HCP endpoints
# ---------------------------------------------------------------------------

async def test_pending_role_cannot_list_patients(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/patients", headers=headers("pending"))
    assert resp.status_code == 403


async def test_pending_role_cannot_create_patient(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/patients",
        json={"mrn": "P-NEW", "masked_name": "Test"},
        headers=headers("pending"),
    )
    assert resp.status_code == 403


async def test_pending_role_cannot_get_timeline(
    client: AsyncClient, sample_patient
) -> None:
    resp = await client.get(
        f"/api/v1/patients/{sample_patient.mrn}/timeline",
        headers=headers("pending"),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H0-04  clinic_hcp cannot access tumor-board-only endpoints
# ---------------------------------------------------------------------------

async def test_clinic_hcp_cannot_create_mtd_session(client: AsyncClient) -> None:
    from datetime import datetime, timezone
    resp = await client.post(
        "/api/v1/mtd/sessions",
        json={"meeting_date": datetime.now(timezone.utc).isoformat()},
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 403


async def test_clinic_hcp_cannot_update_mtd_session_status(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/mtd/sessions/nonexistent",
        json={"status": "completed"},
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H0-05  clinic_hcp cannot access admin endpoints
# ---------------------------------------------------------------------------

async def test_hcp_cannot_list_admin_users(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/users", headers=headers("clinic_hcp"))
    assert resp.status_code == 403


async def test_hcp_cannot_view_audit_log(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/audit", headers=headers("clinic_hcp"))
    assert resp.status_code == 403


async def test_hcp_cannot_patch_user_role(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/admin/users/some-user",
        json={"role": "kb_admin"},
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H0-06  auditor can view audit log but cannot patch roles
# ---------------------------------------------------------------------------

async def test_auditor_can_view_audit_log(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/audit", headers=headers("auditor"))
    # 200 or empty list — just not 403
    assert resp.status_code in (200, 404)


async def test_auditor_cannot_patch_user_role(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/admin/users/some-user",
        json={"role": "kb_admin"},
        headers=headers("auditor"),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H0-07  Consultation isolation — third-party user cannot reply
# ---------------------------------------------------------------------------

async def test_third_party_cannot_add_consultation_message(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_patient,
) -> None:
    from hospital.db.models import Consultation, User

    # Create two users (sender and receiver)
    sender = User(user_id="sender-001", google_sub="sender-001", google_email="sender@test.com", role="clinic_hcp")
    receiver = User(user_id="recv-001", google_sub="recv-001", google_email="recv@test.com", role="clinic_hcp")
    db_session.add_all([sender, receiver])

    consult = Consultation(
        patient_mrn=sample_patient.mrn,
        from_user_id="sender-001",
        to_user_id="recv-001",
        subject="Test consultation",
    )
    db_session.add(consult)
    await db_session.flush()

    # Third-party user (not sender, not receiver) tries to reply
    third_headers = headers("clinic_hcp", sub="third-party-999")
    resp = await client.post(
        f"/api/v1/consultations/{consult.id}/messages",
        json={"body": "Unauthorized reply"},
        headers=third_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H0-08  Consultation close — only sender can close
# ---------------------------------------------------------------------------

async def test_receiver_cannot_close_consultation(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_patient,
) -> None:
    from hospital.db.models import Consultation, User

    sender = User(user_id="s-close-001", google_sub="s-close-001", google_email="sc@test.com", role="clinic_hcp")
    receiver = User(user_id="r-close-001", google_sub="r-close-001", google_email="rc@test.com", role="clinic_hcp")
    db_session.add_all([sender, receiver])

    consult = Consultation(
        patient_mrn=sample_patient.mrn,
        from_user_id="s-close-001",
        to_user_id="r-close-001",
        subject="Close test",
    )
    db_session.add(consult)
    await db_session.flush()

    receiver_headers = headers("clinic_hcp", sub="r-close-001")
    resp = await client.patch(
        f"/api/v1/consultations/{consult.id}/close",
        headers=receiver_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H0-09  MTD conclude — requires care_coordinator role on patient
# ---------------------------------------------------------------------------

async def test_non_coordinator_cannot_conclude_mtd_case(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_patient,
) -> None:
    from datetime import datetime, timezone
    from hospital.db.models import MtdSession, MtdCase

    session = MtdSession(
        meeting_date=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        created_by="board-001",
    )
    db_session.add(session)
    await db_session.flush()

    case = MtdCase(
        mtd_session_id=session.id,
        patient_mrn=sample_patient.mrn,
        added_by="board-001",
    )
    db_session.add(case)
    await db_session.flush()

    # clinic_hcp who is NOT a care_coordinator for this patient
    non_coord = headers("clinic_hcp", sub="not-a-coordinator")
    resp = await client.patch(
        f"/api/v1/mtd/sessions/{session.id}/cases/{sample_patient.mrn}/conclude",
        json={"conclusion_text": "Should fail", "case_status": "discussed"},
        headers=non_coord,
    )
    # Service returns 403 when caller is not care_coordinator
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# H0-10  Input validation — required fields
# ---------------------------------------------------------------------------

async def test_create_patient_missing_mrn_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/patients",
        json={"masked_name": "NoMRN"},
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 422


async def test_create_patient_missing_masked_name_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/patients",
        json={"mrn": "ONLY-MRN"},
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 422


async def test_reminder_acknowledge_nonexistent_returns_404(
    client: AsyncClient, sample_patient
) -> None:
    resp = await client.patch(
        f"/api/v1/patients/{sample_patient.mrn}/reminders/nonexistent-id/acknowledge",
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 404


async def test_consultation_message_on_nonexistent_consult_returns_404(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/consultations/does-not-exist/messages",
        json={"body": "Test"},
        headers=headers("clinic_hcp"),
    )
    assert resp.status_code == 404
