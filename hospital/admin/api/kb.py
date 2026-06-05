"""KB governance endpoints — /api/v1/admin/kb/reviews."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import ADMIN_ROLES, require_role
from hospital.config import get_settings
from hospital.db.models import KbReview
from hospital.db.session import get_db
from hospital.services import audit_service

router = APIRouter(prefix="/admin/kb", tags=["admin"])

# ── KB status helpers ─────────────────────────────────────────────────────────

class KbStatusResponse(BaseModel):
    ok: bool
    total_entities: int
    by_type: dict[str, int]
    schema_errors: int
    ref_errors: int
    contract_errors: int
    last_refreshed_at: datetime | None = None

_last_refreshed_at: datetime | None = None


def _get_kb_status() -> KbStatusResponse:
    from knowledge_base.validation.loader import load_content
    settings = get_settings()
    result = load_content(settings.kb_root_path)
    by_type: dict[str, int] = {}
    for info in result.entities_by_id.values():
        t = info.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return KbStatusResponse(
        ok=result.ok,
        total_entities=len(result.entities_by_id),
        by_type=by_type,
        schema_errors=len(result.schema_errors),
        ref_errors=len(result.ref_errors),
        contract_errors=len(result.contract_errors),
        last_refreshed_at=_last_refreshed_at,
    )


def _do_refresh() -> KbStatusResponse:
    from knowledge_base.validation.loader import clear_load_cache
    global _last_refreshed_at
    clear_load_cache()
    _last_refreshed_at = datetime.now(timezone.utc)
    return _get_kb_status()


# ── KB status / refresh endpoints ─────────────────────────────────────────────

@router.get("/status", response_model=KbStatusResponse)
async def kb_status(
    user: dict = Depends(require_role(ADMIN_ROLES)),
) -> KbStatusResponse:
    """Return current in-process KB load stats without triggering a reload."""
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(None, _get_kb_status)


@router.post("/refresh", response_model=KbStatusResponse)
async def kb_refresh(
    request: Request,
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> KbStatusResponse:
    """Clear the KB loader cache and reload from disk.

    Call after the crawler has written new YAML content to knowledge_base/hosted/content/.
    """
    import asyncio
    result = await asyncio.get_running_loop().run_in_executor(None, _do_refresh)
    await audit_service.log_action(
        db, user_id=user["sub"],
        action="kb.refresh",
        resource_type="kb", resource_id="global",
        diff_summary=f"total={result.total_entities} ok={result.ok} errors={result.schema_errors + result.ref_errors}",
        ip_address=request.client.host if request.client else None,
    )
    return result


@router.post("/crawler-notify", response_model=KbStatusResponse)
async def crawler_notify(
    request: Request,
    x_crawler_secret: str | None = Header(default=None),
) -> KbStatusResponse:
    """Webhook called by the KB crawler after it writes new YAML content.

    Authenticated via HMAC-SHA256 of the request body using CRAWLER_WEBHOOK_SECRET.
    On success, clears the KB loader cache so the next plan generation reads fresh data.
    """
    settings = get_settings()
    if not settings.CRAWLER_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "WEBHOOK_NOT_CONFIGURED"},
        )

    body = await request.body()
    expected = hmac.new(
        settings.CRAWLER_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    provided = (x_crawler_secret or "").removeprefix("sha256=")
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "INVALID_SIGNATURE"},
        )

    import asyncio
    return await asyncio.get_event_loop().run_in_executor(None, _do_refresh)


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
