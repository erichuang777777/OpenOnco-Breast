"""Case management endpoints — /api/v1/cases."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hospital.auth.dependencies import ALL_CLINICAL, HCP_ROLES, require_role
from hospital.db.models import Annotation, Case, Plan
from hospital.db.session import get_db
from hospital.decision.schemas.cases import (
    AnnotationCreate,
    AnnotationSummary,
    CaseCreate,
    CaseResponse,
    PlanSummary,
)
from hospital.services import audit_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Create a new case record."""
    existing = await db.scalar(select(Case).where(Case.mrn == body.mrn))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CASE_ALREADY_EXISTS", "message": f"MRN {body.mrn!r} already registered."},
        )
    case = Case(
        mrn=body.mrn,
        disease_id=body.disease_id,
        last_plan_id=body.initial_plan_id,
        created_by=user["sub"],
    )
    db.add(case)
    await audit_service.log_action(
        db, user_id=user["sub"],
        action=audit_service.CASE_CREATE,
        resource_type="case", resource_id=case.id,
        mrn=body.mrn,
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()
    return _case_to_response(case, [], [])


@router.get("/{mrn}", response_model=CaseResponse)
async def get_case(
    mrn: str,
    user: dict = Depends(require_role(ALL_CLINICAL)),
    db: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Retrieve case summary with plan version chain and annotations."""
    case = await db.scalar(select(Case).where(Case.mrn == mrn))
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CASE_NOT_FOUND", "message": f"MRN {mrn!r} not found."},
        )
    plans_result = await db.scalars(
        select(Plan).where(Plan.mrn == mrn).order_by(Plan.created_at)
    )
    plans = list(plans_result)

    annotations_result = await db.scalars(
        select(Annotation)
        .where(Annotation.plan_id.in_([p.plan_id for p in plans]))
        .order_by(Annotation.created_at)
    )
    annotations = list(annotations_result)
    return _case_to_response(case, plans, annotations)


@router.post("/{mrn}/annotations", response_model=AnnotationSummary, status_code=201)
async def add_annotation(
    mrn: str,
    body: AnnotationCreate,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AnnotationSummary:
    """Append a clinician annotation to a plan (append-only)."""
    plan = await db.scalar(select(Plan).where(Plan.plan_id == body.plan_id))
    if not plan or plan.mrn != mrn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLAN_NOT_FOUND", "message": f"plan_id {body.plan_id!r} not found for MRN {mrn!r}."},
        )
    if body.annotation_type == "select_track" and not body.track_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MISSING_TRACK_ID", "message": "track_id required for select_track annotation."},
        )
    annotation = Annotation(
        plan_id=body.plan_id,
        user_id=user["sub"],
        user_role=body.role,
        annotation_type=body.annotation_type,
        text=body.text,
        track_id=body.track_id,
    )
    db.add(annotation)
    if body.annotation_type == "select_track" and body.track_id:
        plan.selected_track_id = body.track_id
    await audit_service.log_action(
        db, user_id=user["sub"],
        action=audit_service.ANNOTATION_ADD,
        resource_type="annotation", resource_id=annotation.id,
        mrn=mrn,
        diff_summary=f"type={body.annotation_type} plan={body.plan_id}",
    )
    await db.flush()
    return AnnotationSummary(
        id=annotation.id,
        annotation_type=annotation.annotation_type,
        user_id=annotation.user_id,
        user_role=annotation.user_role,
        text=annotation.text,
        track_id=annotation.track_id,
        created_at=annotation.created_at,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _case_to_response(
    case: Case,
    plans: list[Plan],
    annotations: list[Annotation],
) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        mrn=case.mrn,
        disease_id=case.disease_id,
        created_at=case.created_at,
        last_plan_id=case.last_plan_id,
        plans=[
            PlanSummary(
                plan_id=p.plan_id,
                version=p.version,
                created_at=p.created_at,
                created_by=p.created_by,
                supersedes=p.supersedes,
                superseded_by=p.superseded_by,
                revision_trigger=p.revision_trigger,
                selected_track_id=p.selected_track_id,
                status=p.status,
            )
            for p in plans
        ],
        annotations=[
            AnnotationSummary(
                id=a.id,
                annotation_type=a.annotation_type,
                user_id=a.user_id,
                user_role=a.user_role,
                text=a.text,
                track_id=a.track_id,
                created_at=a.created_at,
            )
            for a in annotations
        ],
    )
