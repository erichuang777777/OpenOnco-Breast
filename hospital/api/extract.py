"""LLM extraction endpoint — POST /api/v1/extract."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.schemas.extract import ExtractionRequest, ExtractionResponse
from hospital.services.extraction_service import extract_from_text

router = APIRouter(prefix="/extract", tags=["extract"])


@router.post("", response_model=ExtractionResponse)
async def extract_patient(
    body: ExtractionRequest,
    user: dict = Depends(require_role(HCP_ROLES)),
) -> ExtractionResponse:
    """Convert free-text clinical note to structured patient dict.

    Returns status='complete' with patient dict, or
    status='needs_clarification' with a single clarifying question.
    Max 2 clarification rounds; after that returns complete with remaining gaps.
    """
    try:
        return await extract_from_text(body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "EXTRACTION_UNAVAILABLE",
                "message": "LLM extraction service unavailable. Use structured form.",
                "use_structured_form": True,
            },
        ) from exc
