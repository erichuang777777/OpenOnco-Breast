"""Plan generation API endpoints — POST /api/v1/plan, /plan/gaps, etc."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.decision.schemas.plan import GapsResponse, PlanRequest, PlanResponse, ReviseRequest
from hospital.services import audit_service
from hospital.decision.services.plan_service import (
    compute_gaps,
    generate_plan_response,
    get_stored_plan,
    persist_plan,
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

    mrn_for_storage = body.patient_mrn or body.patient.patient_id
    if mrn_for_storage:
        await persist_plan(
            db, response, mrn=mrn_for_storage, created_by=user["sub"]
        )

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

    if body.patient.patient_id:
        await persist_plan(
            db,
            response,
            mrn=body.patient.patient_id,
            created_by=user["sub"],
            supersedes=plan_id,
        )

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


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Retrieve a previously generated plan by ID.

    Previously unimplemented — the frontend (`ClinicPage`) already called
    this endpoint to reload a saved plan, but it 404'd against FastAPI's
    default routing (no handler existed), and `POST /plan` never
    persisted anything for it to find anyway.
    """
    found = await get_stored_plan(db, plan_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLAN_NOT_FOUND", "message": f"No plan with id {plan_id}"},
        )
    stored, mrn = found

    # Cross-doctor access is allowed (EMR parity, DEVELOPMENT_PLAN.md
    # "Locked design decisions"), but every such access must write an
    # AuditLog row — same requirement as patient-record cross-access.
    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action=audit_service.PLAN_VIEW,
        resource_type="plan",
        resource_id=plan_id,
        mrn=mrn,
        diff_summary=f"viewed plan_id={plan_id}",
        ip_address=request.client.host if request.client else None,
    )
    return stored
