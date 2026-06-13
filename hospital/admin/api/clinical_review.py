"""Clinical sign-off review API.

    GET  /api/v1/admin/kb/unsigned[?entity_type=]        — review queue
    GET  /api/v1/admin/kb/entity/{type}/{id}             — review bundle
    POST /api/v1/admin/kb/entity/{type}/{id}/signoff     — record a decision

The sign-off is recorded in the hospital KbReview table + audit log (the
CHARTER §6.1 two-distinct-reviewer rule). Writing `reviewer_signoffs` back
into the YAML remains a governed git change — this records the auditable
clinical-review decision; it does not mutate the knowledge base.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import ADMIN_ROLES, require_role
from hospital.config import get_settings
from hospital.db.models import KbReview
from hospital.db.session import get_db
from hospital.services import audit_service
from hospital.admin.services import clinical_review as svc

# View: kb_admin + auditor. Sign-off action: kb_admin (Clinical Co-Lead role).
VIEW_ROLES = ADMIN_ROLES + ["auditor"]

router = APIRouter(prefix="/admin/kb", tags=["admin", "clinical-review"])


class UnsignedEntity(BaseModel):
    entity_type: str
    entity_id: str
    label: str
    disease_id: Optional[str] = None
    signoff_count: int
    draft: bool


class UnsignedListResponse(BaseModel):
    total: int
    entities: list[UnsignedEntity]


class SignoffRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    comment: str = ""
    verified_passage: str = ""


class SignoffResponse(BaseModel):
    entity_type: str
    entity_id: str
    review_id: str
    status: str
    reviewer_1: Optional[str] = None
    reviewer_2: Optional[str] = None
    message: str


@router.get("/unsigned", response_model=UnsignedListResponse)
async def list_unsigned(
    entity_type: Optional[str] = None,
    limit: int = 200,
    user: dict = Depends(require_role(VIEW_ROLES)),
) -> UnsignedListResponse:
    settings = get_settings()
    items = svc.list_unsigned(settings.kb_root_path, entity_type)
    return UnsignedListResponse(
        total=len(items),
        entities=[UnsignedEntity(**i) for i in items[:limit]],
    )


@router.get("/entity/{entity_type}/{entity_id}")
async def get_review_bundle(
    entity_type: str,
    entity_id: str,
    user: dict = Depends(require_role(VIEW_ROLES)),
) -> dict:
    settings = get_settings()
    bundle = svc.build_review_bundle(settings.kb_root_path, entity_type, entity_id)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "ENTITY_NOT_FOUND",
                    "message": f"No {entity_type} '{entity_id}'."},
        )
    return bundle


@router.post("/entity/{entity_type}/{entity_id}/signoff", response_model=SignoffResponse)
async def record_signoff(
    entity_type: str,
    entity_id: str,
    body: SignoffRequest,
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> SignoffResponse:
    """Record a clinical reviewer's decision (two distinct reviewers approve →
    'approved'), reusing the KbReview workflow keyed by KB entity."""
    settings = get_settings()
    if svc.build_review_bundle(settings.kb_root_path, entity_type, entity_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "ENTITY_NOT_FOUND",
                    "message": f"No {entity_type} '{entity_id}'."},
        )

    review = await db.scalar(
        select(KbReview)
        .where(KbReview.entity_type == entity_type)
        .where(KbReview.entity_id == entity_id)
        .where(KbReview.status == "pending")
        .order_by(KbReview.submitted_at.desc())
    )
    now = datetime.now(timezone.utc)
    summary = f"clinical sign-off: {body.comment[:120]}" if body.comment else "clinical sign-off review"
    if body.verified_passage:
        summary += f" | verified: {body.verified_passage[:120]}"

    if review is None:
        review = KbReview(
            entity_type=entity_type,
            entity_id=entity_id,
            diff_summary=summary,
            submitted_by=user["sub"],
            status="pending",
        )
        db.add(review)
        await db.flush()

    message = ""
    if body.decision == "approve":
        if review.reviewer_1 is None:
            review.reviewer_1 = user["sub"]
            review.reviewer_1_at = now
            message = "First sign-off recorded. A second distinct reviewer is required (CHARTER §6.1)."
        elif review.reviewer_1 == user["sub"]:
            raise HTTPException(
                status_code=409,
                detail={"error": "ALREADY_REVIEWED",
                        "message": "You already signed off. A second distinct reviewer is required (CHARTER §6.1)."},
            )
        elif review.reviewer_2 is None:
            review.reviewer_2 = user["sub"]
            review.reviewer_2_at = now
            review.status = "approved"
            review.closed_at = now
            message = "Second sign-off recorded — entity approved (pending YAML update via git)."
        action_str = audit_service.KB_REVIEW_APPROVE
    elif body.decision == "reject":
        review.status = "rejected"
        review.closed_at = now
        message = "Marked rejected."
        action_str = audit_service.KB_REVIEW_REJECT
    else:  # request_changes
        review.status = "pending"
        message = "Changes requested."
        action_str = "kb.review.request_changes"

    await audit_service.log_action(
        db,
        user_id=user["sub"],
        action=action_str,
        resource_type="kb_clinical_signoff",
        resource_id=f"{entity_type}/{entity_id}",
        diff_summary=summary,
    )

    return SignoffResponse(
        entity_type=entity_type,
        entity_id=entity_id,
        review_id=review.id,
        status=review.status,
        reviewer_1=review.reviewer_1,
        reviewer_2=review.reviewer_2,
        message=message,
    )
