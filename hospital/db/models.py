"""SQLAlchemy ORM models — see specs/DATABASE_SCHEMA_SPEC.md.

PostgreSQL (prod) / SQLite (MVP).  UUID primary keys represented as TEXT
for SQLite compatibility; UUIDs generated at application layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── cases ─────────────────────────────────────────────────────────────────────

class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    mrn: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    disease_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)
    last_plan_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    fhir_patient_id: Mapped[str | None] = mapped_column(String, nullable=True)

    plans: Mapped[list[Plan]] = relationship(
        "Plan", foreign_keys="Plan.mrn",
        primaryjoin="Case.mrn == Plan.mrn",
        back_populates="case_ref",
        viewonly=True,
    )


# ── plans ─────────────────────────────────────────────────────────────────────

class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','active','superseded','rejected')",
            name="ck_plan_status",
        ),
    )

    plan_id: Mapped[str] = mapped_column(String, primary_key=True)
    mrn: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON str, encrypted in prod
    created_at: Mapped[datetime] = mapped_column(default=_now)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(
        String, ForeignKey("plans.plan_id"), nullable=True
    )
    superseded_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("plans.plan_id"), nullable=True
    )
    revision_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_track_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")

    annotations: Mapped[list[Annotation]] = relationship(
        "Annotation", back_populates="plan", cascade="all, delete-orphan"
    )
    case_ref: Mapped[Case | None] = relationship(
        "Case",
        foreign_keys=[mrn],
        primaryjoin="Plan.mrn == Case.mrn",
        back_populates="plans",
        viewonly=True,
    )


# ── annotations ───────────────────────────────────────────────────────────────

class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint(
            "annotation_type IN ('approve','comment','flag','reject','select_track')",
            name="ck_annotation_type",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(
        String, ForeignKey("plans.plan_id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    user_role: Mapped[str] = mapped_column(String, nullable=False)
    annotation_type: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    track_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    plan: Mapped[Plan] = relationship("Plan", back_populates="annotations")


# ── drug_requisitions ─────────────────────────────────────────────────────────

class DrugRequisition(Base):
    __tablename__ = "drug_requisitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','approved','rejected')",
            name="ck_dreq_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(
        String, ForeignKey("plans.plan_id"), nullable=False, index=True
    )
    mrn: Mapped[str] = mapped_column(String, nullable=False)
    track_id: Mapped[str] = mapped_column(String, nullable=False)
    requisition_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)


# ── audit_log ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(default=_now, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    mrn_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)


# ── kb_reviews ────────────────────────────────────────────────────────────────

class KbReview(Base):
    __tablename__ = "kb_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','withdrawn')",
            name="ck_kbrev_status",
        ),
        CheckConstraint(
            "reviewer_1 IS NULL OR reviewer_2 IS NULL OR reviewer_1 != reviewer_2",
            name="ck_two_distinct_reviewers",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    branch_name: Mapped[str | None] = mapped_column(String, nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diff_summary: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(default=_now)
    reviewer_1: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_1_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewer_2: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_2_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)


# ── users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('pending','tumor_board_hcp','clinic_hcp','kb_admin','auditor')",
            name="ck_user_role",
        ),
    )

    user_id: Mapped[str] = mapped_column(String, primary_key=True)  # = Google sub
    google_sub: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    google_email: Mapped[str] = mapped_column(String, nullable=False)
    google_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auth_provider: Mapped[str] = mapped_column(String, default="google", nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
