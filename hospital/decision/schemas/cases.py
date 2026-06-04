"""Pydantic schemas for case management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


ANNOTATION_TYPES = Literal["approve", "comment", "flag", "reject", "select_track"]


class CaseCreate(BaseModel):
    mrn: str = Field(..., min_length=1)
    disease_id: str = Field(..., examples=["DIS-BREAST"])
    initial_plan_id: Optional[str] = None


class PlanSummary(BaseModel):
    plan_id: str
    version: int
    created_at: datetime
    created_by: str
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    revision_trigger: Optional[str] = None
    selected_track_id: Optional[str] = None
    status: str


class AnnotationSummary(BaseModel):
    id: str
    annotation_type: str
    user_id: str
    user_role: str
    text: Optional[str] = None
    track_id: Optional[str] = None
    created_at: datetime


class CaseResponse(BaseModel):
    id: str
    mrn: str
    disease_id: str
    created_at: datetime
    last_plan_id: Optional[str] = None
    plans: list[PlanSummary] = []
    annotations: list[AnnotationSummary] = []


class AnnotationCreate(BaseModel):
    plan_id: str
    annotation_type: ANNOTATION_TYPES
    text: Optional[str] = None
    role: str = Field(..., examples=["medical_oncologist"])
    track_id: Optional[str] = None   # required when annotation_type="select_track"
