"""Declarative reminder rule engine — Phase B4.

Each rule is an async function that:
  1. Queries patient state from the DB
  2. Decides whether a new reminder is needed
  3. Calls reminder_service.ensure_reminder() — idempotent (no dup if active exists)

Rules are intentionally stateless; the DB is the source of truth.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.db.models import DrugRequisition, HisSyncEvent, Reminder


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Dedup helper ──────────────────────────────────────────────────────────────

async def has_active_reminder(db: AsyncSession, mrn: str, triggered_by: str) -> bool:
    row = await db.scalar(
        select(Reminder).where(
            Reminder.patient_mrn == mrn,
            Reminder.triggered_by == triggered_by,
            Reminder.status == "active",
        )
    )
    return row is not None


async def create_if_not_exists(
    db: AsyncSession,
    *,
    mrn: str,
    reminder_type: str,
    urgency: str,
    title: str,
    due_date: datetime,
    triggered_by: str,
    detail: str | None = None,
) -> Reminder | None:
    if await has_active_reminder(db, mrn, triggered_by):
        return None
    r = Reminder(
        patient_mrn=mrn,
        reminder_type=reminder_type,
        urgency=urgency,
        title=title,
        detail=detail,
        due_date=due_date,
        triggered_by=triggered_by,
    )
    db.add(r)
    await db.flush()
    return r


# ── Rule: drug_reapplication_14d ──────────────────────────────────────────────

async def rule_drug_reapplication_14d(db: AsyncSession, mrn: str) -> Reminder | None:
    """Create reminder if an approved drug requisition expires within 14 days."""
    now = _now()
    window = now + timedelta(days=14)
    rows = await db.scalars(
        select(DrugRequisition).where(
            DrugRequisition.mrn == mrn,
            DrugRequisition.status == "approved",
        )
    )
    for req in rows.all():
        try:
            data = json.loads(req.requisition_json)
            expires_at_str = data.get("expires_at")
            if not expires_at_str:
                continue
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now <= expires_at <= window:
                return await create_if_not_exists(
                    db, mrn=mrn,
                    reminder_type="drug_reapplication",
                    urgency="normal",
                    title="藥物申請即將到期（14 天內）",
                    due_date=expires_at,
                    triggered_by="drug_reapplication_14d",
                )
        except Exception:
            continue
    return None


# ── Rule: drug_reapplication_3d ───────────────────────────────────────────────

async def rule_drug_reapplication_3d(db: AsyncSession, mrn: str) -> Reminder | None:
    """Create HIGH urgency reminder if expiry within 3 days."""
    now = _now()
    window = now + timedelta(days=3)
    rows = await db.scalars(
        select(DrugRequisition).where(
            DrugRequisition.mrn == mrn,
            DrugRequisition.status == "approved",
        )
    )
    for req in rows.all():
        try:
            data = json.loads(req.requisition_json)
            expires_at_str = data.get("expires_at")
            if not expires_at_str:
                continue
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now <= expires_at <= window:
                return await create_if_not_exists(
                    db, mrn=mrn,
                    reminder_type="drug_reapplication",
                    urgency="high",
                    title="藥物申請即將到期（3 天內）",
                    due_date=expires_at,
                    triggered_by="drug_reapplication_3d",
                )
        except Exception:
            continue
    return None


# ── Rule: brca_pending_14d ────────────────────────────────────────────────────

async def rule_brca_pending_14d(db: AsyncSession, mrn: str) -> Reminder | None:
    """Create reminder if BRCA lab ordered 14+ days ago with no result."""
    cutoff = _now() - timedelta(days=14)
    orders = await db.scalars(
        select(HisSyncEvent).where(
            HisSyncEvent.patient_mrn == mrn,
            HisSyncEvent.his_event_type == "lab_result",
            HisSyncEvent.received_at <= cutoff,
        )
    )
    for order in orders.all():
        try:
            data = json.loads(order.payload_json)
            if data.get("lab_type") != "BRCA":
                continue
            if "result" in data:
                continue
            # Check if a result arrived later
            result_row = await db.scalar(
                select(HisSyncEvent).where(
                    HisSyncEvent.patient_mrn == mrn,
                    HisSyncEvent.his_event_type == "lab_result",
                    HisSyncEvent.received_at > order.received_at,
                    HisSyncEvent.payload_json.contains("BRCA"),
                    HisSyncEvent.payload_json.contains("result"),
                )
            )
            if result_row:
                continue
            return await create_if_not_exists(
                db, mrn=mrn,
                reminder_type="brca_result",
                urgency="high",
                title="BRCA 檢驗結果待收（逾 14 天）",
                due_date=_now(),
                triggered_by="brca_pending_14d",
            )
        except Exception:
            continue
    return None


# ── Rule: imaging_followup_due ────────────────────────────────────────────────

async def rule_imaging_followup_due(db: AsyncSession, mrn: str) -> Reminder | None:
    """Create reminder if imaging exam due within 7 days and not yet booked."""
    window = _now() + timedelta(days=7)
    rows = await db.scalars(
        select(HisSyncEvent).where(
            HisSyncEvent.patient_mrn == mrn,
            HisSyncEvent.his_event_type == "appointment",
            HisSyncEvent.payload_json.contains("imaging"),
        )
    )
    for row in rows.all():
        try:
            data = json.loads(row.payload_json)
            if data.get("exam_type") != "imaging":
                continue
            exam_date_str = data.get("exam_date")
            if not exam_date_str:
                continue
            exam_date = datetime.fromisoformat(exam_date_str.replace("Z", "+00:00"))
            if exam_date.tzinfo is None:
                exam_date = exam_date.replace(tzinfo=timezone.utc)
            if _now() <= exam_date <= window and not data.get("booked"):
                return await create_if_not_exists(
                    db, mrn=mrn,
                    reminder_type="imaging_due",
                    urgency="normal",
                    title="影像檢查即將到期",
                    due_date=exam_date,
                    triggered_by="imaging_followup_due",
                )
        except Exception:
            continue
    return None


# ── Rule: followup_appt_7d ────────────────────────────────────────────────────

async def rule_followup_appt_7d(db: AsyncSession, mrn: str) -> Reminder | None:
    """Create reminder if follow-up appointment within 7 days."""
    window = _now() + timedelta(days=7)
    rows = await db.scalars(
        select(HisSyncEvent).where(
            HisSyncEvent.patient_mrn == mrn,
            HisSyncEvent.his_event_type == "appointment",
        )
    )
    for row in rows.all():
        try:
            data = json.loads(row.payload_json)
            appt_date_str = data.get("appt_date")
            if not appt_date_str:
                continue
            appt_date = datetime.fromisoformat(appt_date_str.replace("Z", "+00:00"))
            if appt_date.tzinfo is None:
                appt_date = appt_date.replace(tzinfo=timezone.utc)
            if _now() <= appt_date <= window:
                return await create_if_not_exists(
                    db, mrn=mrn,
                    reminder_type="followup_appt",
                    urgency="normal",
                    title="回診提醒（7 天內）",
                    due_date=appt_date,
                    triggered_by="followup_appt_7d",
                )
        except Exception:
            continue
    return None


# ── Rule: reminder_auto_expire ────────────────────────────────────────────────

async def rule_auto_expire(db: AsyncSession, mrn: str) -> int:
    """Mark past-due active reminders as expired. Returns count expired."""
    now = _now()
    rows = await db.scalars(
        select(Reminder).where(
            Reminder.patient_mrn == mrn,
            Reminder.status == "active",
            Reminder.due_date < now,
        )
    )
    count = 0
    for r in rows.all():
        r.status = "expired"
        count += 1
    if count:
        await db.flush()
    return count


# ── All rules ─────────────────────────────────────────────────────────────────

ALL_RULES = [
    rule_drug_reapplication_14d,
    rule_drug_reapplication_3d,
    rule_brca_pending_14d,
    rule_imaging_followup_due,
    rule_followup_appt_7d,
    rule_auto_expire,
]
