"""KB governance endpoints — /api/v1/admin/kb/reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import ADMIN_ROLES, require_role
from hospital.db.models import KbReview
from hospital.db.session import get_db
from hospital.services import audit_service

router = APIRouter(prefix="/admin/kb", tags=["admin"])


class KbReviewResponse(BaseModel):
    review_id: str
    entity_type: str
    entity_id: str
    branch_name: str | None
    pr_number: int | None
    diff_summary: str
    submitted_by: str
    submitted_at: datetime
    reviewer_1: str | None
    reviewer_2: str | None
    status: str


class KbReviewPatch(BaseModel):
    action: Literal["approve", "reject", "request_changes"]
    comment: str = ""


class KbReviewListResponse(BaseModel):
    pending: list[KbReviewResponse]


@router.get("/reviews", response_model=KbReviewListResponse)
async def list_pending_reviews(
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> KbReviewListResponse:
    result = await db.scalars(
        select(KbReview)
        .where(KbReview.status == "pending")
        .order_by(KbReview.submitted_at)
    )
    reviews = list(result)
    return KbReviewListResponse(pending=[_review_to_response(r) for r in reviews])


@router.patch("/reviews/{review_id}", response_model=KbReviewResponse)
async def action_review(
    review_id: str,
    body: KbReviewPatch,
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> KbReviewResponse:
    """Approve or reject a KB entity review.

    Two distinct approvals required before status changes to 'approved'
    (CHARTER §6.1).
    """
    review = await db.scalar(select(KbReview).where(KbReview.id == review_id))
    if not review:
        raise HTTPException(status_code=404, detail={"error": "REVIEW_NOT_FOUND"})
    if review.status != "pending":
        raise HTTPException(
            status_code=409,
            detail={"error": "REVIEW_CLOSED", "message": f"Review already {review.status}."},
        )

    now = datetime.now(timezone.utc)

    if body.action == "approve":
        if review.reviewer_1 is None:
            review.reviewer_1 = user["sub"]
            review.reviewer_1_at = now
        elif review.reviewer_2 is None and review.reviewer_1 != user["sub"]:
            review.reviewer_2 = user["sub"]
            review.reviewer_2_at = now
            review.status = "approved"
            review.closed_at = now
        elif review.reviewer_1 == user["sub"]:
            raise HTTPException(
                status_code=409,
                detail={"error": "ALREADY_REVIEWED", "message": "You already approved this review. A second distinct reviewer is required (CHARTER §6.1)."},
            )
        action_str = audit_service.KB_REVIEW_APPROVE

    elif body.action == "reject":
        review.status = "rejected"
        review.closed_at = now
        action_str = audit_service.KB_REVIEW_REJECT

    else:  # request_changes
        review.status = "pending"
        action_str = "kb.review.request_changes"

    await audit_service.log_action(
        db, user_id=user["sub"],
        action=action_str,
        resource_type="kb_review", resource_id=review_id,
        diff_summary=f"entity={review.entity_id} action={body.action} comment={body.comment[:80]}",
    )
    return _review_to_response(review)


def _review_to_response(r: KbReview) -> KbReviewResponse:
    return KbReviewResponse(
        review_id=r.id,
        entity_type=r.entity_type,
        entity_id=r.entity_id,
        branch_name=r.branch_name,
        pr_number=r.pr_number,
        diff_summary=r.diff_summary,
        submitted_by=r.submitted_by,
        submitted_at=r.submitted_at,
        reviewer_1=r.reviewer_1,
        reviewer_2=r.reviewer_2,
        status=r.status,
    )
