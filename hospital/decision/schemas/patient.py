"""Pydantic schemas for Patient Registry API (Phase B1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CareTeamMemberCreate(BaseModel):
    user_id: str
    member_role: Literal["primary_hcp", "care_coordinator", "consultant"]
    specialty: str | None = None


class CareTeamMemberResponse(BaseModel):
    id: str
    user_id: str
    member_role: str
    specialty: str | None
    assigned_at: datetime
    assigned_by: str
    active: bool

    model_config = {"from_attributes": True}


class PatientCreate(BaseModel):
    mrn: str
    masked_name: str
    sex: Literal["M", "F", "O"] | None = None
    dob_year: int | None = None
    disease_summary: str | None = None
    status: Literal["active", "discharged", "deceased"] = "active"


class PatientUpdate(BaseModel):
    disease_summary: str | None = None
    status: Literal["active", "discharged", "deceased"] | None = None

    model_config = {"extra": "ignore"}


class PatientResponse(BaseModel):
    mrn: str
    masked_name: str
    sex: str | None
    dob_year: int | None
    disease_summary: str | None
    status: str
    primary_doctor_id: str | None
    his_patient_id: str | None
    his_synced_at: datetime | None
    active_reminder_count: int
    urgent_reminder_count: int
    his_sync_status: str = "unknown"  # "ok" | "stale" | "never" | "unknown"
    care_team: list[CareTeamMemberResponse]
    created_at: datetime
    updated_at: datetime
