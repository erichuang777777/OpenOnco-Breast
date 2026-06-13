"""Plan generation API endpoints — POST /api/v1/plan, /plan/gaps, etc."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.models import Plan
from hospital.db.session import get_db
from hospital.decision.schemas.plan import GapsResponse, PlanRequest, PlanResponse, ReviseRequest
from hospital.services import audit_service
from hospital.decision.services.plan_service import (
    compute_gaps,
    generate_plan_response,
    plan_result_to_json,
)
from hospital.decision.services.timeline_service import add_system_event
from hospital.decision.services.patient_service import get_patient

router = APIRouter(prefix="/plan", tags=["plan"])


async def _persist_plan(
    db: AsyncSession, response: PlanResponse, *, mrn: str, created_by: str
) -> None:
    """Store the generated plan so it can be retrieved by GET /plan/{id}.

    plan_json holds the serialized PlanResponse (PHI — encrypt at rest in
    production, see SECURITY.md). Idempotent on plan_id.
    """
    existing = await db.scalar(select(Plan).where(Plan.plan_id == response.plan_id))
    if existing is not None:
        existing.plan_json = response.model_dump_json()
        return
    db.add(Plan(
        plan_id=response.plan_id,
        mrn=mrn,
        plan_json=response.model_dump_json(),
        created_by=created_by,
        status="draft",
    ))


@router.post("", response_model=PlanResponse)
async def create_plan(
    body: PlanRequest,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Generate a treatment plan from a structured patient profile."""
    # Validate patient_mrn early if provided
    if body.patient_mrn:
        await get_patient(db, body.patient_mrn)

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

    if body.patient_mrn:
        await _persist_plan(
            db, response, mrn=body.patient_mrn, created_by=user["sub"]
        )
        await add_system_event(
            db,
            mrn=body.patient_mrn,
            event_type="onco_query_initiated",
            title="OpenOnco 分析已啟動",
            body_json={"plan_id": response.plan_id},
            source="system_rule",
        )
        await audit_service.log_action(
            db,
            user_id=user["sub"],
            action="onco_query",
            resource_type="plan",
            resource_id=response.plan_id,
            mrn=body.patient_mrn,
            diff_summary=f"onco_query for patient={body.patient_mrn}",
        )

    return response


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Retrieve a previously generated plan by id."""
    row = await db.scalar(select(Plan).where(Plan.plan_id == plan_id))
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "PLAN_NOT_FOUND", "message": f"No plan '{plan_id}'."},
        )
    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action="plan.view",
        resource_type="plan",
        resource_id=plan_id,
        mrn=row.mrn,
        ip_address=request.client.host if request.client else None,
    )
    return PlanResponse(**json.loads(row.plan_json))


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
