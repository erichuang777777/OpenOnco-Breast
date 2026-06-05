"""Consultation schemas — Phase B5."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class ConsultationCreate(BaseModel):
    to_user_id: str
    subject: str

    @field_validator("subject")
    @classmethod
    def subject_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("subject must not be empty")
        return v

    @field_validator("to_user_id")
    @classmethod
    def to_user_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("to_user_id must not be empty")
        return v


class ConsultationMessageCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("body must not be empty")
        return v


class ConsultationMessageResponse(BaseModel):
    id: str
    consultation_id: str
    sender_id: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsultationResponse(BaseModel):
    id: str
    patient_mrn: str
    from_user_id: str
    to_user_id: str
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[ConsultationMessageResponse] = []

    model_config = {"from_attributes": True}
