"""Plan generation API endpoints — POST /api/v1/plan, /plan/gaps, etc."""

from __future__ import annotations

import json as _json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.models import Plan as PlanModel
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

    plan_row = PlanModel(
        plan_id=response.plan_id,
        mrn=body.patient_mrn or (body.patient.patient_id or ""),
        plan_json=_json.dumps(response.model_dump()),
        created_by=user["sub"],
        status="active",
    )
    db.add(plan_row)
    await db.flush()

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
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    row = await db.scalar(sa_select(PlanModel).where(PlanModel.plan_id == plan_id))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLAN_NOT_FOUND"},
        )
    data = _json.loads(row.plan_json)
    response = PlanResponse(**data)
    if row.status != "active":
        stale_warnings = [*response.warnings, f"plan_status:{row.status} — this plan may be outdated"]
        response = response.model_copy(update={"warnings": stale_warnings})
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
    old_plan = await db.scalar(sa_select(PlanModel).where(PlanModel.plan_id == plan_id))
    if not old_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLAN_NOT_FOUND", "message": f"plan_id {plan_id!r} not found"},
        )

    try:
        response = generate_plan_response(body.patient)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ENGINE_NO_ALGORITHM", "message": str(exc)},
        ) from exc

    old_plan.status = "superseded"
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action=audit_service.PLAN_REVISE,
        resource_type="plan",
        resource_id=response.plan_id,
        mrn=body.patient.patient_id,
        diff_summary=f"supersedes={plan_id} trigger={(body.revision_trigger or '')[:80]}",
    )
    return response
