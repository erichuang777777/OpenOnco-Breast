"""Pydantic schemas for drug requisition endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class DrugReqCreate(BaseModel):
    plan_id: str
    track_id: str
    patient_mrn: str = Field(..., min_length=1)
    patient_name_initials: str = Field(
        "", description="De-identified display: 陳O明"
    )
    patient_birth_year: str = ""
    patient_sex: str = ""
    prescribing_physician: str = ""


class DrugComponentResponse(BaseModel):
    drug_id: str
    drug_name_en: str
    brand_name: str
    atc_code: str
    dose: str
    route: str
    schedule: str


class EvidenceResponse(BaseModel):
    nccn_category: str = ""
    nccn_category_zh: str = ""
    esmo_grade: str = ""
    evidence_level: str = ""
    evidence_level_zh: str = ""
    pivotal_trial_nct: list[str] = []
    source_ids: list[str] = []


class DrugReqResponse(BaseModel):
    id: str = ""  # DB primary key — used for preview URL
    requisition_id: str
    created_date: str
    patient_mrn: str
    diagnosis_icd10: str
    diagnosis_text: str
    stage: str
    treatment_intent: str
    line_of_therapy: int
    key_biomarkers: list[str]
    indication_id: str
    plan_id: str
    plan_track_id: str
    regimen_id: str
    regimen_name_en: str
    regimen_name_zh: str
    cycle_length_days: int
    total_cycles: str
    components: list[DrugComponentResponse]
    evidence: EvidenceResponse
    requires_prior_auth: bool
    special_approval_rationale: str
    prescribing_physician: str
    key_toxicities: list[str]


class DrugReqStatusPatch(BaseModel):
    status: str = Field(..., pattern="^(submitted|approved|rejected)$")
    external_ref: Optional[str] = None
