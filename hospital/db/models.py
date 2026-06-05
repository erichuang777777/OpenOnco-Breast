"""SQLAlchemy ORM models — see specs/DATABASE_SCHEMA_SPEC.md.

PostgreSQL (prod) / SQLite (MVP).  UUID primary keys represented as TEXT
for SQLite compatibility; UUIDs generated at application layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
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
    plan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("plans.plan_id"), nullable=True, index=True
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


# ── patients ──────────────────────────────────────────────────────────────────

class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "sex IN ('M','F','O')",
            name="ck_patient_sex",
        ),
        CheckConstraint(
            "status IN ('active','discharged','deceased')",
            name="ck_patient_status",
        ),
    )

    mrn: Mapped[str] = mapped_column(String, primary_key=True)
    masked_name: Mapped[str] = mapped_column(String, nullable=False)
    sex: Mapped[str | None] = mapped_column(String, nullable=True)
    dob_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disease_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    primary_doctor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    his_patient_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    his_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)
    created_by: Mapped[str] = mapped_column(String, nullable=False)

    care_team: Mapped[list["CareTeamMember"]] = relationship(
        "CareTeamMember", back_populates="patient", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        "TimelineEvent", back_populates="patient", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder", back_populates="patient", cascade="all, delete-orphan"
    )
    consultations: Mapped[list["Consultation"]] = relationship(
        "Consultation", back_populates="patient", cascade="all, delete-orphan"
    )
    mtd_cases: Mapped[list["MtdCase"]] = relationship(
        "MtdCase", back_populates="patient"
    )
    his_sync_events: Mapped[list["HisSyncEvent"]] = relationship(
        "HisSyncEvent", back_populates="patient", cascade="all, delete-orphan"
    )


# ── care_team_members ─────────────────────────────────────────────────────────

class CareTeamMember(Base):
    __tablename__ = "care_team_members"
    __table_args__ = (
        UniqueConstraint("patient_mrn", "user_id", name="uq_care_team_patient_user"),
        CheckConstraint(
            "member_role IN ('primary_hcp','care_coordinator','consultant')",
            name="ck_care_team_member_role",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_mrn: Mapped[str] = mapped_column(
        String, ForeignKey("patients.mrn"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    member_role: Mapped[str] = mapped_column(String, nullable=False)
    specialty: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(default=_now)
    assigned_by: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="care_team")


# ── timeline_events ───────────────────────────────────────────────────────────

class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'his_sync','doctor_note','coordinator_note','alert',"
            "'consultation_reply','mtd_conclusion','onco_query_initiated','drug_reminder'"
            ")",
            name="ck_tl_event_type",
        ),
        CheckConstraint(
            "source IN ('his_sync','manual','system_rule')",
            name="ck_tl_source",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_mrn: Mapped[str] = mapped_column(
        String, ForeignKey("patients.mrn"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    event_time: Mapped[datetime] = mapped_column(default=_now, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="timeline_events")


# ── consultations ─────────────────────────────────────────────────────────────

class Consultation(Base):
    __tablename__ = "consultations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','replied','closed')",
            name="ck_consult_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_mrn: Mapped[str] = mapped_column(
        String, ForeignKey("patients.mrn"), nullable=False, index=True
    )
    from_user_id: Mapped[str] = mapped_column(String, nullable=False)
    to_user_id: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="consultations")
    messages: Mapped[list["ConsultationMessage"]] = relationship(
        "ConsultationMessage", back_populates="consultation", cascade="all, delete-orphan"
    )


# ── consultation_messages ─────────────────────────────────────────────────────

class ConsultationMessage(Base):
    __tablename__ = "consultation_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    consultation_id: Mapped[str] = mapped_column(
        String, ForeignKey("consultations.id"), nullable=False, index=True
    )
    sender_id: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    consultation: Mapped["Consultation"] = relationship(
        "Consultation", back_populates="messages"
    )


# ── reminders ─────────────────────────────────────────────────────────────────

class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(
            "reminder_type IN ("
            "'drug_reapplication','pending_lab','imaging_due',"
            "'followup_appt','brca_result','custom'"
            ")",
            name="ck_reminder_type",
        ),
        CheckConstraint(
            "status IN ('active','acknowledged','expired')",
            name="ck_reminder_status",
        ),
        CheckConstraint(
            "urgency IN ('low','normal','high','critical')",
            name="ck_reminder_urgency",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_mrn: Mapped[str] = mapped_column(
        String, ForeignKey("patients.mrn"), nullable=False, index=True
    )
    reminder_type: Mapped[str] = mapped_column(String, nullable=False)
    urgency: Mapped[str] = mapped_column(String, default="normal", nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="reminders")


# ── push_subscriptions ────────────────────────────────────────────────────────

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_endpoint"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(Text, nullable=False)
    auth_key: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)


# ── mtd_sessions ──────────────────────────────────────────────────────────────

class MtdSession(Base):
    __tablename__ = "mtd_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled','in_progress','completed')",
            name="ck_mtd_session_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    meeting_date: Mapped[datetime] = mapped_column(nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="scheduled", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    cases: Mapped[list["MtdCase"]] = relationship(
        "MtdCase", back_populates="session", cascade="all, delete-orphan"
    )


# ── mtd_cases ─────────────────────────────────────────────────────────────────

class MtdCase(Base):
    __tablename__ = "mtd_cases"
    __table_args__ = (
        UniqueConstraint("mtd_session_id", "patient_mrn", name="uq_mtd_case_session_patient"),
        CheckConstraint(
            "status IN ('pending','discussed','deferred')",
            name="ck_mtd_case_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    mtd_session_id: Mapped[str] = mapped_column(
        String, ForeignKey("mtd_sessions.id"), nullable=False, index=True
    )
    patient_mrn: Mapped[str] = mapped_column(
        String, ForeignKey("patients.mrn"), nullable=False, index=True
    )
    added_by: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    conclusion_by: Mapped[str | None] = mapped_column(String, nullable=True)
    conclusion_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    session: Mapped["MtdSession"] = relationship("MtdSession", back_populates="cases")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="mtd_cases")


# ── his_sync_events ───────────────────────────────────────────────────────────

class HisSyncEvent(Base):
    __tablename__ = "his_sync_events"
    __table_args__ = (
        CheckConstraint(
            "his_event_type IN ('appointment','medication','lab_result','imaging','discharge')",
            name="ck_his_event_type",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_mrn: Mapped[str | None] = mapped_column(
        String, ForeignKey("patients.mrn"), nullable=True, index=True
    )
    raw_mrn: Mapped[str] = mapped_column(String, nullable=False, index=True)
    his_event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    sync_source: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    patient: Mapped["Patient | None"] = relationship("Patient", back_populates="his_sync_events")
