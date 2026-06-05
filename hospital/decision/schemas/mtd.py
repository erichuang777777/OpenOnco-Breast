"""MTD schemas — Phase B6."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class MtdSessionCreate(BaseModel):
    meeting_date: datetime
    location: str | None = None

    @field_validator("meeting_date")
    @classmethod
    def meeting_date_required(cls, v: datetime) -> datetime:
        return v


class MtdSessionStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v not in ("scheduled", "in_progress", "completed"):
            raise ValueError("status must be scheduled, in_progress, or completed")
        return v


class MtdCaseCreate(BaseModel):
    patient_mrn: str
    reason: str | None = None

    @field_validator("patient_mrn")
    @classmethod
    def mrn_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("patient_mrn must not be empty")
        return v


class MtdConclude(BaseModel):
    conclusion_text: str
    case_status: str

    @field_validator("case_status")
    @classmethod
    def case_status_valid(cls, v: str) -> str:
        if v not in ("discussed", "deferred"):
            raise ValueError("case_status must be discussed or deferred")
        return v

    @field_validator("conclusion_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("conclusion_text must not be empty")
        return v


class MtdCaseResponse(BaseModel):
    id: str
    mtd_session_id: str
    patient_mrn: str
    added_by: str
    reason: str | None
    status: str
    conclusion_text: str | None
    conclusion_by: str | None
    conclusion_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MtdSessionResponse(BaseModel):
    id: str
    meeting_date: datetime
    location: str | None
    created_by: str
    status: str
    created_at: datetime
    cases: list[MtdCaseResponse] = []

    model_config = {"from_attributes": True}
