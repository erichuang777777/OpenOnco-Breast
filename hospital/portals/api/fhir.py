"""FHIR TW Core patient import — POST /api/v1/fhir/Patient/$import

Accepts a FHIR R4 Patient resource (Taiwan Core profile) and upserts it
into the OpenOnco patient registry.  No external fhir library required —
TW Core is a constrained subset of R4; we parse the JSON directly.

Reference: https://twcore.mohw.gov.tw/ig/twcore/ (CC0)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.models import CareTeamMember, Patient
from hospital.db.session import get_db
from hospital.services import audit_service

router = APIRouter(prefix="/fhir", tags=["fhir"])


# ── TW Core MRN identifier system constants ───────────────────────────────────

_MRN_SYSTEMS = {
    "http://terminology.hl7.org/CodeSystem/v2-0203",      # HL7 v2 (MR code)
    "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Identifier-twcore",
    "urn:oid:2.16.886.101.20003.20004",                    # MOHW OID for MRN
}

_GENDER_MAP = {"male": "M", "female": "F", "other": "O", "unknown": None}


# ── Request / response models ─────────────────────────────────────────────────

class FhirPatientImportRequest(BaseModel):
    """Envelope: either a bare Patient resource or a Bundle containing one."""
    resource: dict[str, Any]
    # Optional: attach to this doctor's care-team automatically
    primary_doctor_id: str | None = None

    @field_validator("resource")
    @classmethod
    def must_be_patient_or_bundle(cls, v: dict) -> dict:
        rt = v.get("resourceType")
        if rt not in ("Patient", "Bundle"):
            raise ValueError(f"resourceType must be Patient or Bundle, got {rt!r}")
        return v


class FhirImportResult(BaseModel):
    mrn: str
    fhir_id: str | None
    action: str           # "created" | "updated"
    masked_name: str
    dob_year: int | None
    sex: str | None
    warnings: list[str]


# ── Mapper ────────────────────────────────────────────────────────────────────

def _extract_patient_resource(resource: dict) -> dict:
    """If resource is a Bundle, extract the first Patient entry."""
    if resource.get("resourceType") == "Patient":
        return resource
    # Bundle — find first Patient entry
    for entry in resource.get("entry", []):
        r = entry.get("resource", {})
        if r.get("resourceType") == "Patient":
            return r
    raise ValueError("Bundle contains no Patient resource")


def _extract_mrn(identifiers: list[dict]) -> str | None:
    """Find MRN from identifier array (TW Core supports multiple identifier types)."""
    for ident in identifiers:
        system = ident.get("system", "")
        type_codings = ident.get("type", {}).get("coding", [])
        is_mr_type = any(c.get("code") == "MR" for c in type_codings)
        is_mrn_system = system in _MRN_SYSTEMS
        if is_mr_type or is_mrn_system:
            val = ident.get("value", "").strip()
            if val:
                return val
    # Fallback: any identifier with a value
    for ident in identifiers:
        val = ident.get("value", "").strip()
        if val:
            return val
    return None


def _extract_name(names: list[dict]) -> str:
    """Extract display name — prefer official use, mask for privacy."""
    official = next((n for n in names if n.get("use") == "official"), None)
    chosen = official or (names[0] if names else {})

    text = chosen.get("text", "").strip()
    if text:
        # Mask all but first character: 王大明 → 王●●
        if len(text) >= 2:
            return text[0] + "●" * (len(text) - 1)
        return text

    # Build from family + given
    family = chosen.get("family", "")
    given = " ".join(chosen.get("given", []))
    full = (family + given).strip()
    if len(full) >= 2:
        return full[0] + "●" * (len(full) - 1)
    return full or "●●"


def _extract_birth_year(birth_date: str | None) -> int | None:
    if not birth_date:
        return None
    # FHIR date can be YYYY, YYYY-MM, or YYYY-MM-DD
    m = re.match(r"^(\d{4})", birth_date)
    return int(m.group(1)) if m else None


def _extract_disease_summary(patient: dict) -> str | None:
    """
    TW Core uses extensions or linked Condition resources for diagnosis.
    We extract from the tw-core-chief-complaint extension if present.
    """
    for ext in patient.get("extension", []):
        url = ext.get("url", "")
        if "chief-complaint" in url or "diagnosis" in url or "condition" in url:
            val = ext.get("valueString") or ext.get("valueCodeableConcept", {}).get("text")
            if val:
                return str(val)
    return None


def map_fhir_patient(raw_resource: dict) -> dict:
    """Map FHIR R4 Patient → OpenOnco patient dict."""
    warnings: list[str] = []

    mrn = _extract_mrn(raw_resource.get("identifier", []))
    if not mrn:
        warnings.append("No MRN identifier found — auto-generating from FHIR id")
        fhir_id = raw_resource.get("id", "")
        mrn = f"FHIR-{fhir_id}" if fhir_id else None
    if not mrn:
        raise ValueError("Cannot determine MRN: no identifier.value and no resource.id")

    masked_name = _extract_name(raw_resource.get("name", []))
    gender_raw = raw_resource.get("gender")
    sex = _GENDER_MAP.get(gender_raw) if gender_raw else None
    if gender_raw and sex is None and gender_raw != "unknown":
        warnings.append(f"Unrecognised gender value {gender_raw!r}; stored as null")

    dob_year = _extract_birth_year(raw_resource.get("birthDate"))
    disease_summary = _extract_disease_summary(raw_resource)
    fhir_id = raw_resource.get("id")

    return {
        "mrn": mrn,
        "fhir_id": fhir_id,
        "masked_name": masked_name,
        "sex": sex,
        "dob_year": dob_year,
        "disease_summary": disease_summary,
        "warnings": warnings,
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/Patient/$import",
    response_model=FhirImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import a FHIR TW Core Patient resource into OpenOnco registry",
)
async def fhir_patient_import(
    body: FhirPatientImportRequest,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> FhirImportResult:
    """
    Accepts a FHIR R4 Patient resource (or a Bundle containing one) conforming
    to the TW Core Implementation Guide and upserts it into the patient registry.

    - If a patient with the same MRN already exists the record is updated.
    - The caller may pass `primary_doctor_id` to assign the patient to a doctor.
    - Names are automatically masked (first character retained, rest replaced with ●).
    """
    try:
        patient_resource = _extract_patient_resource(body.resource)
        mapped = map_fhir_patient(patient_resource)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "FHIR_MAPPING_ERROR", "message": str(exc)},
        ) from exc

    mrn = mapped["mrn"]
    action: str

    existing = await db.scalar(select(Patient).where(Patient.mrn == mrn))
    if existing:
        # Update mutable fields; preserve what's already set if new value is None
        if mapped["masked_name"]:
            existing.masked_name = mapped["masked_name"]
        if mapped["sex"] is not None:
            existing.sex = mapped["sex"]
        if mapped["dob_year"] is not None:
            existing.dob_year = mapped["dob_year"]
        if mapped["disease_summary"]:
            existing.disease_summary = mapped["disease_summary"]
        if mapped["fhir_id"]:
            existing.fhir_patient_id = mapped["fhir_id"]
        existing.updated_at = datetime.now(timezone.utc)
        action = "updated"
    else:
        new_patient = Patient(
            mrn=mrn,
            masked_name=mapped["masked_name"],
            sex=mapped["sex"],
            dob_year=mapped["dob_year"],
            disease_summary=mapped["disease_summary"],
            fhir_patient_id=mapped["fhir_id"],
            status="active",
            primary_doctor_id=body.primary_doctor_id or user["sub"],
            created_by=user["sub"],
        )
        db.add(new_patient)

        # Auto-add importer to care team if not already there
        ct = CareTeamMember(
            patient_mrn=mrn,
            user_id=user["sub"],
            member_role="primary_hcp",
            assigned_by=user["sub"],
        )
        db.add(ct)
        action = "created"

    await db.flush()

    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action=f"fhir_patient_{action}",
        resource_type="patient",
        resource_id=mrn,
        mrn=mrn,
        diff_summary=f"fhir_id={mapped['fhir_id']} action={action}",
        ip_address=request.client.host if request.client else None,
    )

    return FhirImportResult(
        mrn=mrn,
        fhir_id=mapped["fhir_id"],
        action=action,
        masked_name=mapped["masked_name"],
        dob_year=mapped["dob_year"],
        sex=mapped["sex"],
        warnings=mapped["warnings"],
    )
