"""個案管理系統 (CMS) integration adapter — bidirectional FHIR R4.

Inbound  (CMS → OpenOnco):
    fhir_bundle_to_patient(bundle) → patient dict for generate_plan()

Outbound (OpenOnco → CMS):
    plan_result_to_fhir_care_plan(result, patient_fhir_id) → FHIR CarePlan R4

The adapter is deliberately stateless.  All persistence (saving the plan,
queueing the CarePlan PUT back to CMS) is the caller's responsibility.

CHARTER §9.3: this module never writes patient data to disk or logs.
CHARTER §8.3: no clinical decisions are made here; only data reshaping.

FHIR R4 CarePlan spec:
  https://hl7.org/fhir/R4/careplan.html
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .fhir_adapter import (
    extract_patient_id_from_fhir,
    fhir_condition_to_disease_findings,
    fhir_observation_to_findings,
    fhir_patient_to_demographics,
)


# ── Inbound ───────────────────────────────────────────────────────────────────

def fhir_bundle_to_patient(bundle: dict) -> dict:
    """Convert a FHIR R4 Bundle (searchset or collection) into an OpenOnco
    patient dict suitable for `generate_plan()`.

    Expected bundle entry types:
      - Patient           (exactly one)
      - Condition         (primary cancer diagnosis with ICD-10 + stage)
      - Observation       (biomarker / lab results with LOINC codes)

    Unrecognised resources and unmapped codes are silently skipped — the
    engine handles missing fields via its safe-default unknown-findings rule.

    Args:
        bundle: Parsed FHIR Bundle dict (from JSON).

    Returns:
        patient dict with keys: patient_id, disease, demographics,
        findings, biomarkers, line_of_therapy.
    """
    patient: dict[str, Any] = {
        "disease": {},
        "demographics": {},
        "findings": {},
        "biomarkers": {},
        "line_of_therapy": 1,
    }

    entries = bundle.get("entry", [])
    resources = [e.get("resource", {}) for e in entries]

    fhir_patient_res = next(
        (r for r in resources if r.get("resourceType") == "Patient"), None
    )
    if fhir_patient_res:
        patient["patient_id"] = extract_patient_id_from_fhir(fhir_patient_res)
        patient["demographics"].update(
            fhir_patient_to_demographics(fhir_patient_res)
        )

    for res in resources:
        rt = res.get("resourceType", "")

        if rt == "Condition":
            extracted = fhir_condition_to_disease_findings(res)
            if extracted.get("disease"):
                patient["disease"].update(extracted["disease"])
            patient["findings"].update(extracted.get("findings", {}))

        elif rt == "Observation":
            status = res.get("status", "")
            if status in ("registered", "preliminary", "cancelled", "entered-in-error"):
                continue
            patient["findings"].update(fhir_observation_to_findings(res))

        elif rt == "EpisodeOfCare":
            # Extract line of therapy from type coding if present
            for type_entry in res.get("type", []):
                for c in type_entry.get("coding", []):
                    code = c.get("code", "")
                    if code.startswith("line-") and code[5:].isdigit():
                        patient["line_of_therapy"] = int(code[5:])

    # Promote HER2 findings to the top-level biomarkers dict using BIO ids
    # the engine checks — keeps symmetry with hand-authored patient JSONs.
    _promote_her2_biomarker(patient)
    _promote_brca_biomarker(patient)

    return patient


def _promote_her2_biomarker(patient: dict) -> None:
    findings = patient.get("findings", {})
    her2_status = findings.get("her2_status") or findings.get("her2_ihc")
    if her2_status and "BIO-HER2-IHC" not in patient.get("biomarkers", {}):
        if her2_status in ("positive", "3+"):
            patient.setdefault("biomarkers", {})["BIO-HER2-OVEREXPRESSED"] = "positive"


def _promote_brca_biomarker(patient: dict) -> None:
    findings = patient.get("findings", {})
    if findings.get("brca1") == "positive" or findings.get("brca2") == "positive":
        patient.setdefault("biomarkers", {})["BIO-BRCA-GERMLINE"] = "positive"


# ── Outbound ──────────────────────────────────────────────────────────────────

def plan_result_to_fhir_care_plan(
    result: Any,
    patient_fhir_id: str,
    *,
    status: str = "draft",
) -> dict:
    """Serialise a PlanResult as a FHIR R4 CarePlan resource.

    The default status is 'draft' — it must be changed to 'active' by a
    clinician via the CMS after MDT approval (CHARTER §6.1).

    Args:
        result:           PlanResult from generate_plan().
        patient_fhir_id:  The FHIR logical id of the Patient resource in CMS.
        status:           FHIR CarePlan.status ('draft' | 'active' | 'on-hold').

    Returns:
        FHIR R4 CarePlan dict (ready for JSON serialisation and POST/PUT).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    plan = getattr(result, "plan", None)

    care_plan: dict[str, Any] = {
        "resourceType": "CarePlan",
        "id": str(uuid.uuid4()),
        "status": status,
        "intent": "proposal",
        "created": now_iso,
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "title": "OpenOnco Treatment Plan",
        "description": (
            f"Generated by OpenOnco rule engine. "
            f"Disease: {result.disease_id}. "
            f"Algorithm: {result.algorithm_id}."
        ),
        "activity": [],
        "note": [],
        "extension": [
            {
                "url": "https://openonco.info/fhir/StructureDefinition/plan-id",
                "valueString": plan.id if plan else "",
            },
            {
                "url": "https://openonco.info/fhir/StructureDefinition/plan-version",
                "valueInteger": plan.version if plan else 1,
            },
        ],
    }

    if result.warnings:
        for w in result.warnings:
            care_plan["note"].append({"text": f"[WARNING] {w}"})

    if plan and plan.tracks:
        default_tracks = [t for t in plan.tracks if t.is_default]
        alt_tracks = [t for t in plan.tracks if not t.is_default]
        for track in default_tracks + alt_tracks:
            activity = _track_to_fhir_activity(track)
            care_plan["activity"].append(activity)

    # Attach MDT open questions as notes
    if hasattr(result, "mdt") and result.mdt:
        for q in getattr(result.mdt, "open_questions", []):
            blocking = "[BLOCKING] " if getattr(q, "blocking", False) else ""
            care_plan["note"].append({
                "text": f"{blocking}MDT question ({q.owner_role}): {q.question}"
            })

    return care_plan


def _track_to_fhir_activity(track: Any) -> dict:
    """Convert a PlanTrack to a FHIR CarePlan.activity element."""
    label = getattr(track, "label", "") or getattr(track, "label_en", "")
    indication_id = getattr(track, "indication_id", "")
    regimen = getattr(track, "regimen_data", None) or {}
    regimen_name = regimen.get("name", "") if isinstance(regimen, dict) else ""

    activity: dict[str, Any] = {
        "detail": {
            "kind": "MedicationRequest",
            "status": "not-started",
            "doNotPerform": False,
            "description": label,
            "reasonCode": [
                {
                    "coding": [
                        {
                            "system": "https://openonco.info/indication",
                            "code": indication_id,
                            "display": label,
                        }
                    ]
                }
            ],
        },
        "extension": [
            {
                "url": "https://openonco.info/fhir/StructureDefinition/track-id",
                "valueString": getattr(track, "track_id", ""),
            },
            {
                "url": "https://openonco.info/fhir/StructureDefinition/is-default",
                "valueBoolean": bool(getattr(track, "is_default", False)),
            },
        ],
    }

    # Regimen name as productCodeableConcept.text
    if regimen_name:
        activity["detail"]["productCodeableConcept"] = {"text": regimen_name}

    # Source citations as supporting info notes
    sources = []
    if isinstance(regimen, dict):
        sources = regimen.get("sources", []) or []
    if sources:
        activity["detail"]["description"] += (
            f" | Evidence: {', '.join(str(s) for s in sources)}"
        )

    return activity


# ── Decision-gap ServiceRequests ─────────────────────────────────────────────

def decision_gaps_to_fhir_service_requests(
    gaps: list[dict],
    patient_fhir_id: str,
) -> list[dict]:
    """Convert DecisionGapFinder output to FHIR ServiceRequest resources.

    Each gap (a missing biomarker/finding that would change the treatment
    recommendation) becomes a FHIR ServiceRequest with status='draft'.

    Args:
        gaps:             List of dicts with keys: field, rationale, impact.
        patient_fhir_id:  FHIR logical Patient id.

    Returns:
        List of FHIR R4 ServiceRequest dicts.
    """
    requests = []
    for gap in gaps:
        field = gap.get("field", "unknown")
        rationale = gap.get("rationale", "")
        sr: dict[str, Any] = {
            "resourceType": "ServiceRequest",
            "id": str(uuid.uuid4()),
            "status": "draft",
            "intent": "proposal",
            "subject": {"reference": f"Patient/{patient_fhir_id}"},
            "code": {
                "text": field,
                "coding": [
                    {
                        "system": "https://openonco.info/decision-gap",
                        "code": field,
                        "display": field.replace("_", " ").title(),
                    }
                ],
            },
            "note": [{"text": rationale}] if rationale else [],
            "extension": [
                {
                    "url": "https://openonco.info/fhir/StructureDefinition/gap-impact",
                    "valueString": gap.get("impact", ""),
                }
            ],
        }
        requests.append(sr)
    return requests
