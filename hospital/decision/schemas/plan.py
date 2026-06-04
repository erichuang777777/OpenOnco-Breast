"""Pydantic schemas for plan generation and gap analysis endpoints."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request models ────────────────────────────────────────────────────────────

class DiseaseInput(BaseModel):
    id: str = Field(..., examples=["DIS-BREAST"])


class DemographicsInput(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = None
    ecog: Optional[int] = None


class PatientInput(BaseModel):
    patient_id: Optional[str] = None
    disease: DiseaseInput
    line_of_therapy: int = Field(default=1, ge=1, le=10)
    demographics: DemographicsInput = Field(default_factory=DemographicsInput)
    findings: dict[str, Any] = Field(default_factory=dict)
    biomarkers: dict[str, Any] = Field(default_factory=dict)


class PlanRequest(BaseModel):
    patient: PatientInput
    include_mdt: bool = False
    include_gaps: bool = False


class ReviseRequest(BaseModel):
    patient: PatientInput
    revision_trigger: str = Field(..., min_length=5)


# ── Response models ───────────────────────────────────────────────────────────

class TrackResponse(BaseModel):
    track_id: str
    label: str
    label_en: Optional[str] = None
    is_default: bool
    indication_id: str
    regimen_id: Optional[str] = None
    regimen_name: Optional[str] = None
    evidence_level: Optional[str] = None
    nccn_category: Optional[str] = None
    nccn_category_zh: Optional[str] = None
    median_os_months: Optional[float] = None
    selection_reason: Optional[str] = None


class GapItem(BaseModel):
    field: str
    tier: int = Field(..., ge=1, le=3)
    current_value: Any = None
    rationale: str
    if_positive_changes_to: Optional[str] = None
    recommended_test: Optional[str] = None


class MdtRoleSummary(BaseModel):
    required: list[str] = []
    recommended: list[str] = []
    open_questions_count: int = 0
    blocking_questions_count: int = 0


class PlanResponse(BaseModel):
    plan_id: str
    disease_id: str
    algorithm_id: Optional[str] = None
    tracks: list[TrackResponse]
    mdt: Optional[MdtRoleSummary] = None
    gaps: list[GapItem] = []
    warnings: list[str] = []


class GapsResponse(BaseModel):
    gaps: list[GapItem]
