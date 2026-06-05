"""Pydantic schemas for Timeline Events API (Phase B2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


USER_WRITABLE_TYPES = {"doctor_note", "coordinator_note"}
SYSTEM_ONLY_TYPES = {"his_sync", "alert", "mtd_conclusion", "onco_query_initiated", "drug_reminder"}
ALL_EVENT_TYPES = USER_WRITABLE_TYPES | SYSTEM_ONLY_TYPES


class TimelineEventCreate(BaseModel):
    event_type: str
    title: str
    body_json: dict | None = None
    event_time: datetime | None = None

    @field_validator("event_type")
    @classmethod
    def event_type_must_be_user_writable(cls, v: str) -> str:
        if v not in USER_WRITABLE_TYPES:
            raise ValueError(
                f"event_type {v!r} is not user-writable. "
                f"Allowed: {sorted(USER_WRITABLE_TYPES)}"
            )
        return v

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v


class TimelineEventResponse(BaseModel):
    id: str
    patient_mrn: str
    event_type: str
    event_time: datetime
    source: str
    title: str
    body_json: str | None
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
