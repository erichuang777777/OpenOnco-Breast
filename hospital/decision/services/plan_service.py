"""Service layer wrapping knowledge_base.engine.plan.generate_plan().

CHARTER §8.3: the engine—not this service and not any LLM—makes
clinical recommendations.  This module only converts between API
schemas and the engine's patient dict format.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from hospital.config import get_settings
from hospital.decision.services.onco_engine_client import engine as _engine
from hospital.decision.schemas.plan import (
    GapItem,
    MdtRoleSummary,
    PatientInput,
    PlanResponse,
    TrackResponse,
)


def generate_plan(patient_dict: dict, *, kb_root) -> object:
    """Module-level wrapper — patchable in tests, delegates to OncoEngineClient."""
    return _engine.generate_plan(patient_dict, kb_root=kb_root)


def _patient_input_to_dict(patient: PatientInput) -> dict:
    """Convert PatientInput schema → engine patient dict."""
    return {
        "patient_id": patient.patient_id,
        "disease": {"id": patient.disease.id},
        "line_of_therapy": patient.line_of_therapy,
        "demographics": {
            k: v
            for k, v in patient.demographics.model_dump().items()
            if v is not None
        },
        "findings": patient.findings,
        "biomarkers": patient.biomarkers,
    }


def _track_to_response(track) -> TrackResponse:
    regimen = track.regimen_data or {}
    indication = track.indication_data or {}
    outcomes = indication.get("expected_outcomes") or {}
    return TrackResponse(
        track_id=track.track_id,
        label=getattr(track, "label", "") or "",
        label_en=getattr(track, "label_en", None),
        is_default=bool(track.is_default),
        indication_id=track.indication_id,
        regimen_id=regimen.get("id") if isinstance(regimen, dict) else None,
        regimen_name=regimen.get("name") if isinstance(regimen, dict) else None,
        evidence_level=(indication.get("evidence_level") if isinstance(indication, dict) else None),
        nccn_category=(indication.get("nccn_category") if isinstance(indication, dict) else None),
        median_os_months=outcomes.get("median_overall_survival_months"),
        selection_reason=getattr(track, "selection_reason", None),
    )


def generate_plan_response(
    patient: PatientInput,
    *,
    include_mdt: bool = False,
    include_gaps: bool = False,
) -> PlanResponse:
    """Call the engine and return a PlanResponse.

    Raises ValueError if the engine cannot produce a plan.
    """
    settings = get_settings()
    patient_dict = _patient_input_to_dict(patient)

    result = generate_plan(patient_dict, kb_root=settings.kb_root_path)

    if result.plan is None:
        raise ValueError(
            f"Engine returned no plan. Disease: {result.disease_id}, "
            f"Algorithm: {result.algorithm_id}. Warnings: {result.warnings}"
        )

    tracks = [_track_to_response(t) for t in result.plan.tracks]

    mdt_summary = None
    if include_mdt:
        mdt = _engine.orchestrate_mdt(patient_dict, result, kb_root=settings.kb_root_path)
        required = [r.role_id for r in (mdt.required_roles or [])]
        recommended = [r.role_id for r in (mdt.recommended_roles or [])]
        open_q = mdt.open_questions or []
        mdt_summary = MdtRoleSummary(
            required=required,
            recommended=recommended,
            open_questions_count=len(open_q),
            blocking_questions_count=sum(1 for q in open_q if q.blocking),
        )

    gaps: list[GapItem] = []
    if include_gaps:
        gaps = compute_gaps(patient, result)

    return PlanResponse(
        plan_id=result.plan.id,
        disease_id=result.disease_id or "",
        algorithm_id=result.algorithm_id,
        tracks=tracks,
        mdt=mdt_summary,
        gaps=gaps,
        warnings=result.warnings or [],
    )


def compute_gaps(patient: PatientInput, result=None) -> list[GapItem]:
    """Two-pass decision-gap finder.

    For each Tier 2 field not present in patient.findings, re-run the
    engine with that field set to its positive value and compare the
    default indication.  If it changes → surface as a gap.
    """
    settings = get_settings()
    patient_dict = _patient_input_to_dict(patient)

    if result is None:
        result = generate_plan(patient_dict, kb_root=settings.kb_root_path)

    baseline_ind = getattr(
        getattr(result, "default_indication_id", None), "__str__", lambda: None
    )()

    TIER2_PROBES: list[tuple[str, str, dict]] = [
        ("brain_mets", "positive",  {"brain_mets": True}),
        ("brca1",      "positive",  {"brca1": "positive"}),
        ("brca2",      "positive",  {"brca2": "positive"}),
        ("pik3ca_mutation", "positive", {"pik3ca_mutation": "positive"}),
        ("esr1_mutation",   "positive", {"esr1_mutation": "positive"}),
        ("pdl1_cps",   "≥10",       {"pdl1_cps": "10"}),
    ]

    gaps: list[GapItem] = []
    for field, probe_val, probe_findings in TIER2_PROBES:
        if patient.findings.get(field) is not None:
            continue
        hypothetical = dict(patient_dict)
        hypothetical["findings"] = {**patient_dict["findings"], **probe_findings}
        try:
            hyp_result = generate_plan(hypothetical, kb_root=settings.kb_root_path)
            hyp_ind = hyp_result.default_indication_id
            if hyp_ind and hyp_ind != baseline_ind:
                gaps.append(GapItem(
                    field=field,
                    tier=2,
                    current_value=None,
                    rationale=f"If {field}={probe_val}, engine routes to {hyp_ind}",
                    if_positive_changes_to=hyp_ind,
                    recommended_test=_test_for_field(field),
                ))
        except Exception:
            pass  # probe failed — skip, don't block

    return gaps


def _test_for_field(field: str) -> str | None:
    _map = {
        "brca1": "TEST-GERMLINE-BRCA-PANEL",
        "brca2": "TEST-GERMLINE-BRCA-PANEL",
        "brain_mets": "TEST-MRI-BRAIN",
        "pik3ca_mutation": "TEST-PIK3CA-NGS",
        "esr1_mutation": "TEST-ESR1-CTDNA",
        "pdl1_cps": "TEST-PDL1-IHC",
    }
    return _map.get(field)


def plan_result_to_json(result) -> str:
    """Serialise PlanResult to JSON string for DB storage."""
    if hasattr(result, "to_dict"):
        return json.dumps(result.to_dict(), default=str, ensure_ascii=False)
    return json.dumps({}, ensure_ascii=False)
