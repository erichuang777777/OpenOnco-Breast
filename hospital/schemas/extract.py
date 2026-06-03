"""Pydantic schemas for LLM free-text extraction endpoint."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    text: str = Field(..., min_length=3)
    language: Optional[Literal["zh-TW", "en"]] = None   # auto-detect if None
    conversation_id: Optional[str] = None               # None = new conversation


class ExtractedPatient(BaseModel):
    """Partial patient dict as extracted from free text.

    All fields are optional — the extraction may not find everything.
    """
    disease_id: Optional[str] = None
    er_status: Optional[str] = None
    her2_status: Optional[str] = None
    her2_ihc: Optional[str] = None
    her2_ish: Optional[str] = None
    pr_status: Optional[str] = None
    stage_group: Optional[str] = None
    line_of_therapy: Optional[int] = None
    ecog: Optional[int] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    brain_mets: Optional[bool] = None
    brca1: Optional[str] = None
    brca2: Optional[str] = None
    pik3ca_mutation: Optional[str] = None
    esr1_mutation: Optional[str] = None
    pdl1_cps: Optional[Any] = None


class ExtractionGap(BaseModel):
    field: str
    tier: int
    description: str


class ExtractionResponse(BaseModel):
    conversation_id: str
    status: Literal["complete", "needs_clarification"]
    patient: Optional[ExtractedPatient] = None
    gaps: list[ExtractionGap] = []
    # set when status == "needs_clarification"
    question: Optional[str] = None
    missing_field: Optional[str] = None


class ConversationState(BaseModel):
    """In-memory conversation state (keyed by conversation_id, TTL 30 min)."""
    conversation_id: str
    turns: int = 0
    extracted_so_far: ExtractedPatient = Field(default_factory=ExtractedPatient)
    asked_fields: list[str] = []
    input_language: str = "zh-TW"
