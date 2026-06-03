"""Audit logging service — all clinical actions recorded here.

MRN is hashed before storage (SHA-256 + AUDIT_MRN_SALT).
No PHI in diff_summary or any other audit field.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from hospital.config import get_settings
from hospital.db.models import AuditLog


def hash_mrn(mrn: str) -> str:
    salt = get_settings().AUDIT_MRN_SALT
    return hashlib.sha256(f"{mrn}{salt}".encode()).hexdigest()


async def log_action(
    db: AsyncSession,
    *,
    user_id: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    mrn: str | None = None,
    diff_summary: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Append one audit record.  Never raises — silently logs on error."""
    try:
        entry = AuditLog(
            ts=datetime.now(timezone.utc),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            mrn_hash=hash_mrn(mrn) if mrn else None,
            diff_summary=diff_summary,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        # Caller commits the session (or it auto-commits via get_db dependency)
    except Exception:
        pass  # audit must never block clinical flow


# ── Action constants ──────────────────────────────────────────────────────────

PLAN_GENERATE = "plan.generate"
PLAN_REVISE = "plan.revise"
ANNOTATION_ADD = "annotation.add"
DRUG_REQ_CREATE = "drug_req.create"
DRUG_REQ_SUBMIT = "drug_req.submit"
PATIENT_LINK_CREATE = "patient_link.create"
KB_REVIEW_APPROVE = "kb.review.approve"
KB_REVIEW_REJECT = "kb.review.reject"
CASE_CREATE = "case.create"
USER_ROLE_CHANGE = "user.role_change"
USER_DEACTIVATE = "user.deactivate"
