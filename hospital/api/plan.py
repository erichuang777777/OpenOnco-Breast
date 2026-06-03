"""Plan generation API endpoints — POST /api/v1/plan, /plan/gaps, etc."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.schemas.plan import GapsResponse, PlanRequest, PlanResponse, ReviseRequest
from hospital.services import audit_service
from hospital.services.plan_service import (
    compute_gaps,
    generate_plan_response,
    plan_result_to_json,
)

router = APIRouter(prefix="/plan", tags=["plan"])


@router.post("", response_model=PlanResponse)
async def create_plan(
    body: PlanRequest,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Generate a treatment plan from a structured patient profile."""
    try:
        response = generate_plan_response(
            body.patient,
            include_mdt=body.include_mdt,
            include_gaps=body.include_gaps,
        )
    except ValueError as exc:
        msg = str(exc)
        if "no plan" in msg.lower() or "no algorithm" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "ENGINE_NO_ALGORITHM", "message": msg},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_PATIENT_DICT", "message": msg},
        ) from exc

    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action=audit_service.PLAN_GENERATE,
        resource_type="plan",
        resource_id=response.plan_id,
        mrn=body.patient.patient_id,
        diff_summary=f"disease={response.disease_id} algorithm={response.algorithm_id}",
        ip_address=request.client.host if request.client else None,
    )
    return response


@router.post("/gaps", response_model=GapsResponse)
async def get_decision_gaps(
    body: PlanRequest,
    user: dict = Depends(require_role(HCP_ROLES)),
) -> GapsResponse:
    """Run two-pass gap finder.  Returns missing fields that would change recommendation."""
    try:
        gaps = compute_gaps(body.patient)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ENGINE_ERROR", "message": str(exc)},
        ) from exc
    return GapsResponse(gaps=gaps)


@router.post("/{plan_id}/revise", response_model=PlanResponse)
async def revise_plan(
    plan_id: str,
    body: ReviseRequest,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Generate a next-version plan superseding an existing one."""
    try:
        response = generate_plan_response(body.patient)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ENGINE_NO_ALGORITHM", "message": str(exc)},
        ) from exc

    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action=audit_service.PLAN_REVISE,
        resource_type="plan",
        resource_id=response.plan_id,
        mrn=body.patient.patient_id,
        diff_summary=f"supersedes={plan_id} trigger={body.revision_trigger[:80]}",
    )
    return response
