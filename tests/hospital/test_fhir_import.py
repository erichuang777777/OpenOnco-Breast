"""Tests for FHIR TW Core patient import endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from hospital.portals.api.fhir import map_fhir_patient


def _hdr(role: str = "clinic_hcp", sub: str = "user-001") -> dict:
    from hospital.auth.jwt_utils import create_access_token
    token = create_access_token(sub, f"{sub}@hospital.tw", "Test User", role)
    return {"Authorization": f"Bearer {token}"}


# ── Unit tests for the mapper ─────────────────────────────────────────────────

def test_map_standard_twcore_patient():
    resource = {
        "resourceType": "Patient",
        "id": "twcore-001",
        "identifier": [
            {
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]},
                "value": "MRN-FHIR-001",
            }
        ],
        "name": [{"use": "official", "text": "王大明"}],
        "gender": "male",
        "birthDate": "1971",
    }
    mapped = map_fhir_patient(resource)
    assert mapped["mrn"] == "MRN-FHIR-001"
    assert mapped["sex"] == "M"
    assert mapped["dob_year"] == 1971
    assert mapped["masked_name"] == "王●●"
    assert mapped["fhir_id"] == "twcore-001"
    assert mapped["warnings"] == []


def test_map_masks_long_name():
    resource = {
        "resourceType": "Patient",
        "id": "x",
        "identifier": [{"value": "MRN-X"}],
        "name": [{"use": "official", "text": "陳建志"}],
        "gender": "male",
        "birthDate": "1980-05",
    }
    mapped = map_fhir_patient(resource)
    assert mapped["masked_name"] == "陳●●"
    assert mapped["dob_year"] == 1980


def test_map_female_patient():
    resource = {
        "resourceType": "Patient",
        "id": "y",
        "identifier": [{"value": "MRN-Y"}],
        "name": [{"use": "official", "text": "李●"}],
        "gender": "female",
        "birthDate": "1968-09-15",
    }
    mapped = map_fhir_patient(resource)
    assert mapped["sex"] == "F"
    assert mapped["dob_year"] == 1968


def test_map_no_mrn_uses_fhir_id():
    resource = {
        "resourceType": "Patient",
        "id": "auto-001",
        "name": [{"use": "official", "text": "張●"}],
        "gender": "other",
    }
    mapped = map_fhir_patient(resource)
    assert mapped["mrn"] == "FHIR-auto-001"
    assert "No MRN identifier found" in mapped["warnings"][0]


def test_map_unknown_gender_warns():
    resource = {
        "resourceType": "Patient",
        "id": "z",
        "identifier": [{"value": "MRN-Z"}],
        "name": [{"use": "official", "text": "趙●"}],
        "gender": "nonbinary",
    }
    mapped = map_fhir_patient(resource)
    assert mapped["sex"] is None
    assert any("nonbinary" in w for w in mapped["warnings"])


def test_map_bundle_extracts_patient():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Observation"}},
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "bund-001",
                    "identifier": [{"value": "MRN-B001"}],
                    "name": [{"use": "official", "text": "吳●"}],
                    "gender": "female",
                }
            },
        ],
    }
    from hospital.portals.api.fhir import _extract_patient_resource
    patient_res = _extract_patient_resource(bundle)
    assert patient_res["resourceType"] == "Patient"
    assert patient_res["id"] == "bund-001"


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fhir_import_creates_patient(client: AsyncClient):
    resource = {
        "resourceType": "Patient",
        "id": "int-001",
        "identifier": [
            {"type": {"coding": [{"code": "MR"}]}, "value": "MRN-INT-001"}
        ],
        "name": [{"use": "official", "text": "黃素芳"}],
        "gender": "female",
        "birthDate": "1985",
    }
    resp = await client.post(
        "/api/v1/fhir/Patient/$import",
        json={"resource": resource},
        headers=_hdr(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mrn"] == "MRN-INT-001"
    assert body["action"] == "created"
    assert body["sex"] == "F"
    assert body["dob_year"] == 1985
    assert body["masked_name"] == "黃●●"


@pytest.mark.asyncio
async def test_fhir_import_upserts_existing(client: AsyncClient):
    resource = {
        "resourceType": "Patient",
        "id": "int-002",
        "identifier": [{"value": "MRN-INT-002"}],
        "name": [{"use": "official", "text": "趙秀"}],
        "gender": "female",
        "birthDate": "1990",
    }
    r1 = await client.post("/api/v1/fhir/Patient/$import", json={"resource": resource}, headers=_hdr())
    assert r1.json()["action"] == "created"

    # Second import of same MRN → update
    r2 = await client.post("/api/v1/fhir/Patient/$import", json={"resource": resource}, headers=_hdr())
    assert r2.status_code == 200
    assert r2.json()["action"] == "updated"


@pytest.mark.asyncio
async def test_fhir_import_rejects_update_from_other_care_team(client: AsyncClient):
    """A second HCP must not be able to overwrite another team's patient.

    Without an ownership check this endpoint is an IDOR: knowing an MRN is
    enough to rewrite name, sex, birth year, diagnosis summary and FHIR id,
    bypassing the check PATCH /patients/{mrn} enforces.
    """
    resource = {
        "resourceType": "Patient",
        "id": "int-003",
        "identifier": [{"value": "MRN-INT-003"}],
        "name": [{"use": "official", "text": "林原"}],
        "gender": "female",
        "birthDate": "1980",
    }
    created = await client.post(
        "/api/v1/fhir/Patient/$import", json={"resource": resource}, headers=_hdr(sub="owner-001")
    )
    assert created.json()["action"] == "created"

    # A different HCP, not on the care team, tries to overwrite the record.
    tampered = {**resource, "name": [{"use": "official", "text": "假名"}], "gender": "male"}
    resp = await client.post(
        "/api/v1/fhir/Patient/$import", json={"resource": tampered}, headers=_hdr(sub="intruder-001")
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "NOT_ON_CARE_TEAM"

    # And the record must be untouched.
    check = await client.get("/api/v1/patients/MRN-INT-003", headers=_hdr(sub="owner-001"))
    assert check.status_code == 200
    assert check.json()["masked_name"] == "林●"
    assert check.json()["sex"] == "F"


@pytest.mark.asyncio
async def test_fhir_import_allows_update_by_owner(client: AsyncClient):
    """The primary doctor keeps being able to update their own patient."""
    resource = {
        "resourceType": "Patient",
        "id": "int-004",
        "identifier": [{"value": "MRN-INT-004"}],
        "name": [{"use": "official", "text": "陳明"}],
        "gender": "male",
        "birthDate": "1975",
    }
    await client.post("/api/v1/fhir/Patient/$import", json={"resource": resource}, headers=_hdr(sub="owner-002"))
    again = await client.post(
        "/api/v1/fhir/Patient/$import", json={"resource": resource}, headers=_hdr(sub="owner-002")
    )
    assert again.status_code == 200
    assert again.json()["action"] == "updated"


@pytest.mark.asyncio
async def test_fhir_import_rejects_wrong_resource_type(client: AsyncClient):
    resp = await client.post(
        "/api/v1/fhir/Patient/$import",
        json={"resource": {"resourceType": "Observation"}},
        headers=_hdr(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_fhir_import_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/fhir/Patient/$import",
        json={"resource": {"resourceType": "Patient"}},
    )
    assert resp.status_code in (401, 403)
