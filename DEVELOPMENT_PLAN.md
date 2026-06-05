# OpenOnco Hospital Edition — Development Plan

**Version:** 0.1  
**Date:** 2026-06-04  
**Status:** Active  
**Scope:** `hospital/` backend + `frontend/` React SPA  

---

## Locked design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cross-doctor patient access | Allowed (EMR-parity). Every cross-doctor access **must** write an `AuditLog` row. No other restriction. | Hospital EMRs already allow this; audit trail covers accountability. |
| HIS crawler | This repo defines `hospital/portals/his_adapter.py` (stub interface only). Crawler lives in a separate repo. | Same pattern as `hospital/compute/adapter.py`. |
| Doctor notifications | **PWA Web Push** (VAPID) + in-app reminder badge count. | Confirmed feasible via service worker push on both desktop and mobile. |
| OpenOnco recommendation | Doctor must explicitly click "查詢循證建議". Never auto-populated. | CHARTER §8.3: AI/rule engine is not the autonomous decision-maker. |
| Frontend | React + Vite + TypeScript. OpenAPI → generated TS types. MSW for mocking in tests. | Decoupled from Jinja2; works as PWA installable app. |
| Database | SQLite (MVP pilot) / PostgreSQL (production). One-line config switch. | Matches `HOSPITAL_SYSTEM_SPEC.md §5`. |

---

## Gate rule (non-negotiable)

Before starting Phase N+1, all of the following must exit 0:

```bash
pytest tests/hospital/ --asyncio-mode=auto -x -q   # backend gate
```

For frontend phases additionally:
```bash
cd frontend && npm run typecheck && npm run test -- --run   # frontend gate
```

No test may be silenced with `pytest.skip()` unless decorated  
`@pytest.mark.skip(reason="blocked until phase BN")` with a forward reference.

---

## Phase overview

| ID | Name | New test file(s) | Est. |
|----|------|-----------------|------|
| B0 | Schema expansion | `test_models_b0.py` | 2 d |
| B1 | Patient registry API | `test_patient_api.py` | 3 d |
| B2 | Timeline events API | `test_timeline_api.py` | 2 d |
| B3 | HIS adapter interface | `test_his_adapter.py` | 1 d |
| B4 | Reminder engine | `test_reminder_engine.py` | 3 d |
| B5 | Consultations | `test_consultations.py` | 2 d |
| B6 | MTD management | `test_mtd.py` | 2 d |
| B7 | Push notifications | `test_push_api.py` | 2 d |
| B8 | OpenOnco enhancement | `test_onco_link.py` | 1 d |
| F0 | React scaffold | build + typecheck pass | 2 d |
| F1 | Auth flow (frontend) | `auth.test.tsx` | 1 d |
| F2 | Patient list page | `patient-list.test.tsx` | 2 d |
| F3 | Patient detail page | `patient-detail.test.tsx` | 3 d |
| F4 | Tumor board page | `board.test.tsx` | 2 d |
| F5 | OpenOnco analysis page | `clinic.test.tsx` | 2 d |
| F6 | Drug requisition flow | `drug-req.test.tsx` | 1 d |
| F7 | Admin pages | `admin.test.tsx` | 2 d |
| E0 | E2E scaffold (Playwright) | config + smoke | 1 d |
| E1 | Critical path E2E | `critical-path.spec.ts` | 3 d |
| H0 | Security hardening | `test_security.py` | 2 d |

---

## Phase B0 — Schema Expansion

### Goal
Add all new ORM models required by the CRM vision.  
No API changes — pure DB layer.  
All models validated by constraint tests before any route is built.

### New files
- `hospital/db/models.py` — extend with new tables
- `hospital/db/migrations/` — Alembic migration for new tables
- `tests/hospital/test_models_b0.py`

### New ORM models

#### `Patient`
```
patient_mrn   TEXT PK               -- masked in display layer, not here
masked_name   TEXT NOT NULL         -- e.g. "王●●"
sex           TEXT CHECK IN (M,F,O)
dob_year      INT nullable
disease_summary TEXT nullable       -- denormalised for list view
status        TEXT DEFAULT 'active' CHECK IN (active,discharged,deceased)
primary_doctor_id TEXT FK users.user_id
created_at    DATETIME
updated_at    DATETIME
```

#### `CareTeamMember`
```
id              TEXT PK uuid
patient_mrn     TEXT FK patients.patient_mrn
user_id         TEXT FK users.user_id
member_role     TEXT CHECK IN (primary_hcp, care_coordinator, consultant)
assigned_at     DATETIME
assigned_by     TEXT FK users.user_id
UNIQUE(patient_mrn, user_id)
```

#### `TimelineEvent`
```
id            TEXT PK uuid
patient_mrn   TEXT FK patients.patient_mrn INDEX
event_type    TEXT CHECK IN (
                his_sync, doctor_note, coordinator_note,
                alert, consultation_reply, mtd_conclusion,
                onco_query_initiated, drug_reminder
              )
event_time    DATETIME INDEX
source        TEXT CHECK IN (his_sync, manual, system_rule)
title         TEXT NOT NULL
body_json     TEXT nullable     -- JSON payload
created_by    TEXT nullable     -- NULL for system-generated
created_at    DATETIME
```

#### `Consultation`
```
id            TEXT PK uuid
patient_mrn   TEXT FK patients.patient_mrn INDEX
from_user_id  TEXT FK users.user_id
to_user_id    TEXT FK users.user_id
subject       TEXT NOT NULL
status        TEXT DEFAULT 'open' CHECK IN (open, replied, closed)
created_at    DATETIME
updated_at    DATETIME
```

#### `ConsultationMessage`
```
id                TEXT PK uuid
consultation_id   TEXT FK consultations.id INDEX
sender_id         TEXT FK users.user_id
body              TEXT NOT NULL
created_at        DATETIME
```

#### `Reminder`
```
id              TEXT PK uuid
patient_mrn     TEXT FK patients.patient_mrn INDEX
reminder_type   TEXT CHECK IN (
                  drug_reapplication, pending_lab, imaging_due,
                  followup_appt, brca_result, custom
                )
title           TEXT NOT NULL
detail          TEXT nullable
due_date        DATETIME NOT NULL INDEX
status          TEXT DEFAULT 'active' CHECK IN (active, acknowledged, expired)
triggered_by    TEXT NOT NULL         -- rule name, e.g. "drug_reapplication_14d"
acknowledged_by TEXT nullable FK users.user_id
acknowledged_at DATETIME nullable
created_at      DATETIME
```

#### `PushSubscription`
```
id          TEXT PK uuid
user_id     TEXT FK users.user_id INDEX
endpoint    TEXT NOT NULL UNIQUE
p256dh_key  TEXT NOT NULL
auth_key    TEXT NOT NULL
user_agent  TEXT nullable
active      BOOLEAN DEFAULT TRUE
created_at  DATETIME
```

#### `MtdSession`
```
id            TEXT PK uuid
meeting_date  DATE NOT NULL
location      TEXT nullable
created_by    TEXT FK users.user_id
status        TEXT DEFAULT 'scheduled' CHECK IN (scheduled, in_progress, completed)
created_at    DATETIME
```

#### `MtdCase`
```
id               TEXT PK uuid
mtd_session_id   TEXT FK mtd_sessions.id INDEX
patient_mrn      TEXT FK patients.patient_mrn
added_by         TEXT FK users.user_id
reason           TEXT nullable
status           TEXT DEFAULT 'pending' CHECK IN (pending, discussed, deferred)
conclusion_by    TEXT nullable FK users.user_id
conclusion_at    DATETIME nullable
created_at       DATETIME
UNIQUE(mtd_session_id, patient_mrn)
```

#### `HisSyncEvent`
```
id            TEXT PK uuid
patient_mrn   TEXT FK patients.patient_mrn INDEX
his_event_type TEXT CHECK IN (appointment, medication, lab_result, imaging, discharge)
payload_json  TEXT NOT NULL
sync_source   TEXT NOT NULL    -- e.g. "his_adapter_mock"
received_at   DATETIME NOT NULL INDEX
processed_at  DATETIME nullable
```

### Tests — `tests/hospital/test_models_b0.py`

```python
test_patient_create_and_retrieve                  # basic insert + select
test_patient_mrn_is_primary_key                   # duplicate MRN raises IntegrityError
test_patient_status_constraint_rejects_invalid    # 'unknown' raises CheckConstraint
test_care_team_unique_constraint                  # duplicate (mrn, user_id) raises
test_care_team_member_roles_constraint            # 'nurse' raises CheckConstraint
test_timeline_event_all_types_accepted            # each of 8 types inserts OK
test_timeline_event_invalid_type_rejected         # 'unknown' raises CheckConstraint
test_consultation_status_transitions              # open→replied→closed OK; open→closed OK
test_consultation_message_cascade_delete          # delete consultation deletes messages
test_reminder_type_constraint                     # each valid type accepted
test_reminder_status_constraint                   # 'ignored' raises CheckConstraint
test_push_subscription_endpoint_unique            # duplicate endpoint raises
test_mtd_session_status_constraint                # 'cancelled' raises CheckConstraint
test_mtd_case_unique_per_session                  # duplicate (session, mrn) raises
test_his_sync_event_type_constraint               # 'vitals' raises CheckConstraint
test_all_new_tables_created_via_create_all        # Base.metadata.create_all succeeds for all models
test_foreign_key_patient_mrn_enforced             # CareTeamMember with unknown mrn raises
```

### Gate
```bash
pytest tests/hospital/test_models_b0.py --asyncio-mode=auto -x -q
```

---

## Phase B1 — Patient Registry API

### Goal
Full CRUD for the `patients` table and `care_team_members` table.  
Patient list returns only patients where the caller is on the care team (or `primary_doctor`).  
Cross-doctor reads are allowed but **every** such access writes an `AuditLog` row.

### New files
- `hospital/decision/schemas/patient.py`
- `hospital/decision/services/patient_service.py`
- `hospital/decision/api/patients.py`
- `tests/hospital/test_patient_api.py`

### API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/patients` | any HCP | List caller's patients (care-team member or primary doctor). Accepts `?tab=all\|followup\|consulted\|mtd\|alerts`. |
| `POST` | `/api/v1/patients` | clinic_hcp | Create new patient record |
| `GET` | `/api/v1/patients/{mrn}` | any HCP | Get single patient. Writes AuditLog if caller not on care team. |
| `PATCH` | `/api/v1/patients/{mrn}` | clinic_hcp, tumor_board_hcp | Update disease_summary, status |
| `GET` | `/api/v1/patients/{mrn}/care-team` | any HCP | List care team |
| `POST` | `/api/v1/patients/{mrn}/care-team` | primary_doctor only | Add care team member |
| `DELETE` | `/api/v1/patients/{mrn}/care-team/{user_id}` | primary_doctor only | Remove member |

### Response shape — `GET /api/v1/patients` (one row)
```json
{
  "patient_mrn": "A12●●●47",
  "masked_name": "王●●",
  "disease_summary": "乳癌 HER2+ · 第四期",
  "status": "active",
  "primary_doctor_id": "user-001",
  "care_team": [{"user_id": "...", "member_role": "care_coordinator"}],
  "active_reminder_count": 2,
  "urgent_reminder_count": 1,
  "next_event_title": "回診評估",
  "next_event_date": "2026-06-10"
}
```

### Tests — `tests/hospital/test_patient_api.py`

```python
# --- list ---
test_patient_list_returns_only_my_patients            # HCP sees only own patients
test_patient_list_tab_consulted_returns_inbound       # returns patients where I am to_user on open consultation
test_patient_list_tab_mtd_returns_scheduled           # returns patients in upcoming MtdSession
test_patient_list_tab_alerts_returns_urgent_reminders # returns patients with urgent active reminders
test_patient_list_empty_for_new_user                  # fresh user sees empty list
test_patient_list_includes_care_team_members          # care_coordinator also sees patient
test_patient_list_excludes_unrelated_doctor           # unrelated doctor does NOT see patient in own list
test_patient_list_requires_auth                       # 401 without token

# --- create ---
test_patient_create_success_201                       # HCP creates patient, gets 201 + location header
test_patient_create_sets_primary_doctor               # created_by becomes primary_doctor_id
test_patient_create_duplicate_mrn_409                 # second create with same MRN → 409
test_patient_create_pending_role_403                  # pending role cannot create
test_patient_create_invalid_status_422                # unknown status enum → 422

# --- get single ---
test_patient_get_own_patient_200                      # primary doctor reads own patient
test_patient_get_cross_doctor_allowed_200             # other doctor can read
test_patient_get_cross_doctor_writes_audit_log        # cross-doctor read → AuditLog row exists with action='patient_cross_access'
test_patient_get_care_team_member_no_audit_log        # care team member read does NOT write cross-access audit
test_patient_get_unknown_mrn_404                      # unknown MRN → 404
test_patient_get_requires_auth                        # 401 without token

# --- patch ---
test_patient_patch_disease_summary                    # HCP updates disease_summary
test_patient_patch_status_to_discharged               # HCP sets status=discharged
test_patient_patch_unknown_field_ignored              # extra field in body does not raise
test_patient_patch_invalid_status_422                 # unknown enum → 422
test_patient_patch_non_team_member_allowed            # any HCP can patch (EMR-parity) + audit log

# --- care team ---
test_care_team_list_returns_members                   # lists all members
test_care_team_add_member_201                         # primary doctor adds coordinator
test_care_team_add_duplicate_409                      # re-adding same user → 409
test_care_team_add_by_non_primary_403                 # non-primary doctor cannot add
test_care_team_remove_success_204                     # primary doctor removes member
test_care_team_remove_self_allowed                    # primary doctor can remove themselves
test_care_team_remove_nonexistent_404                 # removing unknown user → 404
```

### Gate
```bash
pytest tests/hospital/test_models_b0.py tests/hospital/test_patient_api.py \
       --asyncio-mode=auto -x -q
```

---

## Phase B2 — Timeline Events API

### Goal
Append-only event log per patient.  
Doctors and coordinators can add manual entries.  
System rules add events (HIS sync stubs, alerts) via a service function.

### New files
- `hospital/decision/schemas/timeline.py`
- `hospital/decision/services/timeline_service.py`
- `hospital/decision/api/timeline.py`
- `tests/hospital/test_timeline_api.py`

### API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/patients/{mrn}/timeline` | any HCP | List events, newest first. `?type=doctor_note` filter. `?limit=50&offset=0`. |
| `POST` | `/api/v1/patients/{mrn}/timeline` | any HCP | Add manual event (doctor_note or coordinator_note) |

`POST` body:
```json
{
  "event_type": "doctor_note",     // or "coordinator_note"
  "title": "門診記錄",
  "body_json": {"text": "C2 耐受性良好…"},
  "event_time": "2026-06-04T09:00:00Z"   // optional, defaults to now
}
```

`POST` restriction: only `doctor_note` / `coordinator_note` are user-writable.  
`his_sync`, `alert`, `mtd_conclusion`, `onco_query_initiated`, `drug_reminder` are system-only (service-layer only, no direct API write).

### Tests — `tests/hospital/test_timeline_api.py`

```python
# --- list ---
test_timeline_list_returns_events_newest_first      # events sorted descending by event_time
test_timeline_list_filter_by_type                   # ?type=doctor_note returns only doctor_notes
test_timeline_list_pagination                        # limit+offset works
test_timeline_list_unknown_mrn_404
test_timeline_list_requires_auth

# --- create doctor_note ---
test_timeline_post_doctor_note_201
test_timeline_post_sets_created_by_from_jwt         # created_by = caller user_id
test_timeline_post_custom_event_time_accepted
test_timeline_post_missing_title_422
test_timeline_post_empty_title_422
test_timeline_post_unknown_mrn_404

# --- create coordinator_note ---
test_timeline_post_coordinator_note_201
test_timeline_post_coordinator_note_type_stored

# --- system-only types rejected from API ---
test_timeline_post_his_sync_type_rejected_422
test_timeline_post_alert_type_rejected_422
test_timeline_post_mtd_conclusion_type_rejected_422

# --- service layer (direct, bypasses HTTP) ---
test_timeline_service_add_his_sync_event            # service fn writes his_sync event
test_timeline_service_add_alert_event               # service fn writes alert event
test_timeline_service_add_mtd_conclusion_event      # service fn writes mtd_conclusion
test_timeline_service_add_onco_query_event          # service fn writes onco_query_initiated
```

### Gate
```bash
pytest tests/hospital/test_models_b0.py tests/hospital/test_patient_api.py \
       tests/hospital/test_timeline_api.py --asyncio-mode=auto -x -q
```

---

## Phase B3 — HIS Adapter Interface

### Goal
Define the adapter stub and data contract for inbound HIS events.  
No real HIS connection — stub raises `NotImplementedError` (same as `compute/adapter.py`).  
One inbound webhook endpoint for a mock HIS to POST events to.

### New files
- `hospital/portals/his_adapter.py` — adapter stub
- `hospital/portals/his_ingestion.py` — parses payload → `HisSyncEvent` + `TimelineEvent`
- `hospital/portals/api/his_webhook.py` — `POST /api/v1/his/ingest`
- `tests/hospital/test_his_adapter.py`

### Adapter interface (`his_adapter.py`)
```python
class HisAdapter:
    def get_patient_appointments(self, mrn: str) -> list[dict]: raise NotImplementedError
    def get_patient_medications(self, mrn: str) -> list[dict]: raise NotImplementedError
    def get_lab_results(self, mrn: str) -> list[dict]: raise NotImplementedError
    def get_imaging_results(self, mrn: str) -> list[dict]: raise NotImplementedError

his_adapter = HisAdapter()
```

### Webhook endpoint

`POST /api/v1/his/ingest`  
Auth: shared secret header `X-HIS-Secret` (configured in settings).  
Body: `{"event_type": "appointment", "mrn": "A12●●●47", "payload": {...}}`  
→ Writes `HisSyncEvent` + `TimelineEvent(event_type='his_sync')` + triggers reminder rule evaluation.

### Tests — `tests/hospital/test_his_adapter.py`

```python
# --- adapter contract ---
test_his_adapter_get_appointments_raises_not_implemented
test_his_adapter_get_medications_raises_not_implemented
test_his_adapter_get_lab_results_raises_not_implemented
test_his_adapter_get_imaging_raises_not_implemented

# --- ingestion service ---
test_ingestion_appointment_creates_his_sync_event
test_ingestion_appointment_creates_timeline_event
test_ingestion_unknown_mrn_creates_event_with_unmatched_flag
test_ingestion_medication_event_stored
test_ingestion_lab_result_event_stored
test_ingestion_imaging_event_stored

# --- webhook ---
test_his_webhook_valid_secret_200
test_his_webhook_wrong_secret_401
test_his_webhook_missing_secret_401
test_his_webhook_malformed_json_422
test_his_webhook_unknown_event_type_422
test_his_webhook_stores_his_sync_event_in_db
test_his_webhook_creates_timeline_event_in_db
test_his_webhook_idempotent_on_duplicate_payload    # same payload twice → stored once

# --- patient list tab (requires HIS appointment data — moved from B1) ---
test_patient_list_tab_followup_filters_correctly    # returns patients with upcoming appointments from his_sync_events
```

### Gate
```bash
pytest tests/hospital/test_models_b0.py tests/hospital/test_patient_api.py \
       tests/hospital/test_timeline_api.py tests/hospital/test_his_adapter.py \
       --asyncio-mode=auto -x -q
```

---

## Phase B4 — Reminder Engine

### Goal
Declarative rule engine that evaluates patient state → creates / expires `Reminder` rows.  
Rules run on: HIS ingest event, manual trigger (API), and a cron endpoint.

### New files
- `hospital/decision/services/reminder_rules.py` — rule definitions
- `hospital/decision/services/reminder_service.py` — evaluate + CRUD
- `hospital/decision/api/reminders.py`
- `tests/hospital/test_reminder_engine.py`

### Rules (each rule = one test)

| Rule ID | Trigger | Condition | Reminder type | Due offset |
|---------|---------|-----------|---------------|-----------|
| `drug_reapplication_14d` | cron / HIS med event | active drug requisition expires ≤ 14 days | `drug_reapplication` | expiry date |
| `drug_reapplication_3d` | cron | active drug requisition expires ≤ 3 days | `drug_reapplication` | expiry date, urgency=high |
| `brca_pending_14d` | timeline event `his_sync` with lab_type=BRCA | no result after 14 days | `brca_result` | +14 days from order |
| `imaging_followup_due` | HIS appointment event | imaging exam due date within 7 days, not booked | `imaging_due` | exam due date |
| `followup_appt_7d` | cron | next appointment within 7 days | `followup_appt` | appt date |
| `reminder_auto_expire` | cron | reminder.due_date < now AND status=active | — | marks status=expired |

### API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/patients/{mrn}/reminders` | any HCP | List reminders. `?status=active` filter. |
| `PATCH` | `/api/v1/patients/{mrn}/reminders/{id}/acknowledge` | any HCP | Acknowledge a reminder |
| `POST` | `/api/v1/patients/{mrn}/reminders` | any HCP | Create custom reminder |
| `POST` | `/api/v1/admin/reminders/evaluate` | kb_admin | Force-run all rules for all patients |

### Tests — `tests/hospital/test_reminder_engine.py`

```python
# --- rule: drug_reapplication ---
test_rule_drug_reapplication_14d_creates_reminder
test_rule_drug_reapplication_3d_creates_reminder_with_high_urgency
test_rule_drug_reapplication_no_duplicate_if_active_reminder_exists
test_rule_drug_reapplication_no_reminder_if_expiry_far_away

# --- rule: BRCA pending ---
test_rule_brca_pending_creates_reminder_after_14_days
test_rule_brca_pending_no_reminder_if_result_received
test_rule_brca_pending_no_reminder_within_14_days

# --- rule: imaging followup ---
test_rule_imaging_followup_creates_reminder_7_days_before
test_rule_imaging_followup_no_reminder_if_already_booked

# --- rule: followup appointment ---
test_rule_followup_appt_creates_reminder_7d_before
test_rule_followup_appt_no_reminder_if_no_upcoming_appt

# --- auto expiry ---
test_rule_auto_expire_marks_past_due_reminders_expired
test_rule_auto_expire_does_not_touch_acknowledged_reminders

# --- service layer ---
test_reminder_service_evaluate_all_rules_for_patient
test_reminder_service_no_duplicate_active_reminder_same_type_and_patient

# --- API: list ---
test_reminder_list_returns_active_reminders
test_reminder_list_filter_status_active
test_reminder_list_filter_status_expired
test_reminder_list_unknown_mrn_404

# --- API: acknowledge ---
test_reminder_acknowledge_sets_status_acknowledged
test_reminder_acknowledge_sets_acknowledged_by_and_at
test_reminder_acknowledge_already_acknowledged_idempotent
test_reminder_acknowledge_unknown_id_404

# --- API: custom create ---
test_reminder_custom_create_201
test_reminder_custom_create_missing_title_422
test_reminder_custom_create_past_due_date_422

# --- API: force evaluate ---
test_reminder_admin_evaluate_runs_all_rules
test_reminder_admin_evaluate_requires_kb_admin
```

### Gate
```bash
pytest tests/hospital/test_models_b0.py tests/hospital/test_patient_api.py \
       tests/hospital/test_timeline_api.py tests/hospital/test_his_adapter.py \
       tests/hospital/test_reminder_engine.py --asyncio-mode=auto -x -q
```

---

## Phase B5 — Consultations

### Goal
Doctor-to-doctor async consultation scoped to a patient.  
Sending a consultation adds the recipient to the patient's "被諮詢" view.  
Reply creates a `TimelineEvent(event_type='consultation_reply')`.

### New files
- `hospital/decision/schemas/consultation.py`
- `hospital/decision/services/consultation_service.py`
- `hospital/decision/api/consultations.py`
- `tests/hospital/test_consultations.py`

### API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/patients/{mrn}/consultations` | any HCP | List all consultations for patient |
| `POST` | `/api/v1/patients/{mrn}/consultations` | any HCP | Create consultation (from=caller, to=to_user_id) |
| `GET` | `/api/v1/consultations` | any HCP | My consultations (sent or received). `?role=sent\|received\|all`. |
| `POST` | `/api/v1/consultations/{id}/messages` | from_user OR to_user | Add reply message |
| `PATCH` | `/api/v1/consultations/{id}/close` | from_user only | Close consultation |

### Tests — `tests/hospital/test_consultations.py`

```python
# --- create ---
test_consultation_create_201
test_consultation_create_from_is_caller
test_consultation_create_unknown_to_user_404
test_consultation_create_unknown_mrn_404
test_consultation_create_pending_role_403

# --- list per patient ---
test_consultation_list_per_patient_returns_all
test_consultation_list_per_patient_unknown_mrn_404

# --- my consultations ---
test_my_consultations_received_returns_inbound
test_my_consultations_sent_returns_outbound
test_my_consultations_all_returns_both

# --- reply message ---
test_consultation_reply_creates_message
test_consultation_reply_updates_status_to_replied
test_consultation_reply_creates_timeline_event     # TimelineEvent(event_type='consultation_reply') written
test_consultation_reply_by_third_party_403         # unrelated doctor cannot reply
test_consultation_reply_to_closed_consultation_409

# --- close ---
test_consultation_close_by_sender_204
test_consultation_close_sets_status_closed
test_consultation_close_by_recipient_403
test_consultation_close_already_closed_idempotent

# --- patient list integration ---
test_patient_list_tab_consulted_includes_consultation_patient
    # When doctor B has open inbound consultation for patient owned by doctor A,
    # patient appears in doctor B's "被諮詢" tab
```

### Gate
```bash
pytest tests/hospital/test_models_b0.py tests/hospital/test_patient_api.py \
       tests/hospital/test_timeline_api.py tests/hospital/test_his_adapter.py \
       tests/hospital/test_reminder_engine.py tests/hospital/test_consultations.py \
       --asyncio-mode=auto -x -q
```

---

## Phase B6 — MTD Management

### Goal
Care coordinator creates MTD sessions and adds patients.  
Any HCP can read; only care coordinator (member_role=care_coordinator) can write conclusions.  
Conclusion write-back creates `TimelineEvent(event_type='mtd_conclusion')` visible to all care team.

### New files
- `hospital/decision/schemas/mtd.py`
- `hospital/decision/services/mtd_service.py`
- `hospital/decision/api/mtd.py`
- `tests/hospital/test_mtd.py`

### API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/mtd/sessions` | any HCP | List sessions. `?status=scheduled`. |
| `POST` | `/api/v1/mtd/sessions` | tumor_board_hcp | Create MTD session |
| `GET` | `/api/v1/mtd/sessions/{id}` | any HCP | Get session with cases |
| `POST` | `/api/v1/mtd/sessions/{id}/cases` | tumor_board_hcp | Add patient to session |
| `PATCH` | `/api/v1/mtd/sessions/{id}/cases/{mrn}/conclude` | care_coordinator on patient | Write MTD conclusion |
| `PATCH` | `/api/v1/mtd/sessions/{id}` | tumor_board_hcp | Update status (→ in_progress / completed) |

`PATCH /conclude` body:
```json
{
  "conclusion_text": "委員會一致同意繼續 THP…",
  "case_status": "discussed"   // or "deferred"
}
```
→ creates `TimelineEvent(event_type='mtd_conclusion', body_json={conclusion_text, session_id, meeting_date})`

### Tests — `tests/hospital/test_mtd.py`

```python
# --- session CRUD ---
test_mtd_session_create_201
test_mtd_session_create_requires_tumor_board_role
test_mtd_session_list_returns_sessions
test_mtd_session_list_filter_by_status
test_mtd_session_get_unknown_404

# --- add case ---
test_mtd_add_case_201
test_mtd_add_case_duplicate_409
test_mtd_add_case_unknown_mrn_404
test_mtd_add_case_unknown_session_404
test_mtd_add_case_requires_tumor_board_role

# --- conclude ---
test_mtd_conclude_sets_case_status_discussed
test_mtd_conclude_sets_conclusion_by_and_at
test_mtd_conclude_creates_timeline_event
test_mtd_conclude_timeline_event_body_contains_conclusion_text
test_mtd_conclude_timeline_event_body_contains_meeting_date
test_mtd_conclude_by_non_care_coordinator_403
test_mtd_conclude_deferred_status_stored
test_mtd_conclude_already_concluded_idempotent

# --- session status ---
test_mtd_session_status_to_in_progress
test_mtd_session_status_to_completed
test_mtd_session_invalid_status_422

# --- patient list integration ---
test_patient_list_tab_mtd_includes_patient_in_upcoming_session
    # Patient added to scheduled MtdSession within 7 days appears in 待MTD tab
```

### Gate
```bash
pytest tests/hospital/ --asyncio-mode=auto -x -q
# (all existing + new phase tests)
```

---

## Phase B7 — Push Notifications

### Goal
PWA Web Push via VAPID.  
Users subscribe from the browser; backend stores endpoint + keys.  
A notification dispatcher sends pushes when urgent reminders are created or due.

### New files
- `hospital/services/push_service.py` — VAPID sender (uses `pywebpush`)
- `hospital/decision/api/push.py`
- `tests/hospital/test_push_api.py`

### Settings additions
```ini
VAPID_PRIVATE_KEY=...    # generated at deploy time
VAPID_PUBLIC_KEY=...
VAPID_SUBJECT=mailto:admin@hospital.tw
```

### API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/push/vapid-public-key` | any HCP | Return base64 VAPID public key for browser |
| `POST` | `/api/v1/push/subscribe` | any HCP | Store push subscription |
| `DELETE` | `/api/v1/push/subscribe` | any HCP | Unsubscribe (body: `{endpoint}`) |
| `GET` | `/api/v1/push/subscriptions` | any HCP | List own subscriptions |

### Trigger rules
When a reminder with `urgency=high` is created OR a reminder transitions to `due_date < now + 1h`:  
`push_service.notify_user(user_id, title, body)` is called for all active subscriptions of that user.

### Tests — `tests/hospital/test_push_api.py`

```python
# --- VAPID public key ---
test_push_vapid_public_key_200
test_push_vapid_public_key_returns_non_empty_string
test_push_vapid_public_key_requires_auth

# --- subscribe ---
test_push_subscribe_201
test_push_subscribe_duplicate_endpoint_idempotent  # same endpoint → 200, not 201
test_push_subscribe_missing_endpoint_422
test_push_subscribe_missing_p256dh_422
test_push_subscribe_missing_auth_key_422

# --- unsubscribe ---
test_push_unsubscribe_204
test_push_unsubscribe_unknown_endpoint_404
test_push_unsubscribe_other_user_subscription_404  # user B cannot delete user A's sub

# --- list ---
test_push_list_own_subscriptions
test_push_list_does_not_include_other_users

# --- dispatch service (mocked sender) ---
test_push_service_notify_calls_webpush_for_active_sub
test_push_service_notify_skips_inactive_sub
test_push_service_notify_marks_sub_inactive_on_410_gone  # endpoint expired → active=False
test_push_service_notify_no_subscriptions_no_error

# --- trigger integration ---
test_urgent_reminder_create_triggers_push           # creating high-urgency reminder calls push_service.notify_user
test_non_urgent_reminder_does_not_trigger_push
test_reminder_due_soon_triggers_push                # cron evaluation for due_date < now+1h
```

### Gate
```bash
pytest tests/hospital/ --asyncio-mode=auto -x -q
```

---

## Phase B8 — OpenOnco Enhancement

### Goal
When a doctor initiates an OpenOnco query, link the resulting plan to the patient record  
and write a `TimelineEvent(event_type='onco_query_initiated')`.  
The doctor's identity is recorded as `created_by`.

### Changed files
- `hospital/decision/api/plan.py` — add optional `patient_mrn` param
- `hospital/decision/services/plan_service.py` — write timeline event on plan creation
- `tests/hospital/test_onco_link.py`

### API change
`POST /api/v1/plan` — add optional field `patient_mrn: str | None`.  
If provided and patient exists → creates timeline event + links `Plan.mrn = patient_mrn`.  
If patient not found → 404 (fail explicitly; do not silently drop).

### Tests — `tests/hospital/test_onco_link.py`

```python
test_plan_without_patient_mrn_still_works           # existing behaviour unbroken
test_plan_with_valid_patient_mrn_creates_timeline_event
test_plan_timeline_event_type_is_onco_query_initiated
test_plan_timeline_event_body_contains_plan_id
test_plan_timeline_event_created_by_is_caller
test_plan_with_unknown_patient_mrn_404
test_plan_links_plan_mrn_to_patient_mrn
test_plan_audit_log_written_for_onco_query          # AuditLog row with action='onco_query'
test_multiple_plans_for_same_patient_all_appear_in_timeline
```

### Gate (full backend suite)
```bash
pytest tests/hospital/ --asyncio-mode=auto -x -q
# All hospital tests green = backend complete
```

---

## Phase F0 — React Scaffold

### Goal
Vite + React + TypeScript project under `frontend/`.  
OpenAPI spec auto-generates TypeScript types.  
MSW configured for API mocking in tests.  
Vitest configured for component tests.  
PWA plugin installed (`vite-plugin-pwa`).

### New files/dirs
```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  src/
    api/           # generated types from /openapi.json
    components/
    pages/
    hooks/
    App.tsx
    main.tsx
  public/
    manifest.json  # same as mockups/manifest.json, production version
  tests/
    setup.ts       # MSW server setup
  e2e/             # Playwright
    playwright.config.ts
```

### Gate
```bash
cd frontend
npm ci
npm run typecheck       # tsc --noEmit: 0 errors
npm run build           # vite build: exit 0, dist/ produced
npm run test -- --run   # vitest: 0 test failures
# Note: Playwright E2E scaffold is Phase E0 — not gated here
```

---

## Phase F1 — Auth Flow (Frontend)

### Goal
Login page (Google OAuth redirect).  
JWT stored in httpOnly cookie (backend sets it).  
Auth guard: redirect to `/login` if no valid token.  
Role stored in React context, used to show/hide UI elements.

### Tests — `frontend/tests/auth.test.tsx`

```typescript
test_login_page_renders_google_button
test_login_page_shows_pending_notice_for_new_accounts   // MSW: role=pending response
test_auth_guard_redirects_unauthenticated_to_login      // navigate to /patients → /login
test_auth_context_provides_role_to_children
test_auth_context_clinic_hcp_sees_patient_list_link
test_auth_context_tumor_board_sees_board_link
test_auth_context_kb_admin_sees_admin_link
test_logout_clears_auth_context
test_token_expired_redirects_to_login                   // MSW: 401 on any API call
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
```

---

## Phase F2 — Patient List Page

### Goal
`/patients` route — renders the patient list with tabs, stat cards, reminder dots.  
Tab filtering sends `?tab=` query to API.  
Clicking a row navigates to `/patients/:mrn`.  
Stat cards (total / followup / urgent / MTD) driven from API aggregate.

### Tests — `frontend/tests/patient-list.test.tsx`

```typescript
// All tests use MSW to mock GET /api/v1/patients
test_patient_list_renders_mrn_column
test_patient_list_renders_masked_name
test_patient_list_renders_disease_summary
test_patient_list_renders_status_chip
test_patient_list_renders_next_action
test_patient_list_renders_care_info
test_patient_list_renders_reminder_dots_urgent       // urgent_reminder_count > 0 → red dot
test_patient_list_renders_reminder_dots_warn         // non-urgent → amber dot
test_patient_list_no_dots_when_no_reminders
test_patient_list_stat_card_total
test_patient_list_stat_card_urgent
test_patient_list_stat_card_followup
test_patient_list_stat_card_mtd
test_patient_list_tab_all_selected_by_default
test_patient_list_tab_click_changes_active_tab
test_patient_list_tab_click_sends_correct_query_param
test_patient_list_empty_state_shown_when_no_patients
test_patient_list_row_click_navigates_to_detail
test_patient_list_loading_state_shown
test_patient_list_error_state_shown
test_patient_list_sync_badge_shows_his_source
test_patient_list_consulted_row_has_distinct_style   // 被諮詢 row has blue tint
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
```

---

## Phase F3 — Patient Detail Page

### Goal
`/patients/:mrn` — patient header, event timeline, right sidebar  
(reminders panel, OpenOnco initiation button, consultations).  
Timeline is paginated; "load more" fetches next page.  
New note textarea + save/MTD/consult action buttons.  
OpenOnco button navigates to `/patients/:mrn/onco`.

### Tests — `frontend/tests/patient-detail.test.tsx`

```typescript
// MSW: GET /api/v1/patients/:mrn, GET /api/v1/patients/:mrn/timeline,
//      GET /api/v1/patients/:mrn/reminders, GET /api/v1/patients/:mrn/consultations
test_detail_renders_mrn_in_header
test_detail_renders_masked_name
test_detail_renders_status_chips
test_detail_renders_team_avatars
test_detail_renders_his_sync_timestamp
test_detail_back_button_navigates_to_list

// --- timeline ---
test_timeline_renders_coordinator_note_with_highlighted_style
test_timeline_renders_doctor_note
test_timeline_renders_his_sync_as_system_event_italics
test_timeline_renders_alert_event_with_warning_style
test_timeline_renders_mtd_conclusion_event
test_timeline_renders_consultation_reply_event
test_timeline_load_more_fetches_next_page
test_timeline_note_input_is_present
test_timeline_save_button_posts_to_api
test_timeline_save_clears_textarea_after_success
test_timeline_mtd_button_opens_mtd_flow
test_timeline_consult_button_opens_consultation_flow

// --- reminders panel ---
test_reminders_panel_shows_urgent_count_badge
test_reminders_panel_renders_drug_reminder
test_reminders_panel_renders_brca_reminder
test_reminders_panel_renders_imaging_reminder
test_reminders_panel_acknowledge_button_calls_api
test_reminders_panel_acknowledged_reminder_visually_removed

// --- OpenOnco initiation ---
test_onco_init_button_is_visible
test_onco_init_button_shows_last_query_timestamp
test_onco_init_button_navigates_to_onco_page
test_onco_init_no_auto_population               // No plan data shown until button clicked

// --- consultations ---
test_consultations_panel_shows_open_and_replied
test_consultations_new_button_opens_form
test_consultations_create_form_submits_to_api
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
```

---

## Phase F4 — Tumor Board Page

### Goal
`/board` — MTD session list, case table with status chips, expanded case discussion.

### Tests — `frontend/tests/board.test.tsx`

```typescript
test_board_renders_case_table
test_board_case_row_shows_mrn_masked
test_board_case_row_shows_status_chip
test_board_case_row_shows_plan_summary
test_board_expanded_case_shows_recommendation_panel
test_board_expanded_case_shows_annotation_timeline
test_board_add_annotation_posts_to_api
test_board_conclude_button_requires_tumor_board_role
test_board_new_session_button_creates_session
test_board_export_agenda_button_present
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
```

---

## Phase F5 — OpenOnco Analysis Page

### Goal
`/patients/:mrn/onco` — the full evidence analysis view (refactored from `clinic.html`).  
Loaded only when doctor explicitly navigates here.  
Breadcrumb: ← 返回個案.  
Shows extracted fields, decision gaps, two treatment tracks, citations.

### Tests — `frontend/tests/clinic.test.tsx`

```typescript
test_clinic_page_shows_breadcrumb_back_to_patient
test_clinic_page_shows_patient_mrn_in_header
test_clinic_page_renders_extracted_fields_grid
test_clinic_field_confirmed_shows_tick
test_clinic_field_missing_shows_add_button
test_clinic_gap_banner_shown_when_gaps_present
test_clinic_gap_banner_hidden_when_no_gaps
test_clinic_standard_track_rendered
test_clinic_aggressive_track_rendered
test_clinic_track_nccn_classification_chip
test_clinic_track_citations_shown
test_clinic_select_track_button_posts_to_api
test_clinic_audit_log_written_on_page_load   // MSW verifies POST to audit endpoint
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
```

---

## Phase F6 — Drug Requisition Flow

### Goal
`/patients/:mrn/drug-req` — create and submit drug requisition.  
Linked to reminders: creating from a reminder acknowledges it.

### Tests — `frontend/tests/drug-req.test.tsx`

```typescript
test_drug_req_form_renders_track_name
test_drug_req_form_renders_patient_info
test_drug_req_submit_posts_to_api
test_drug_req_submit_acknowledges_linked_reminder
test_drug_req_status_draft_shown
test_drug_req_status_submitted_shown_after_submit
test_drug_req_validation_requires_track
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
```

---

## Phase F7 — Admin Pages

### Goal
`/admin` — user role management, KB review queue, audit log viewer.

### Tests — `frontend/tests/admin.test.tsx`

```typescript
test_admin_user_list_renders_email_and_role
test_admin_user_role_patch_submits_to_api
test_admin_user_pending_shown_distinctly
test_admin_kb_review_list_renders_entity_type
test_admin_kb_review_approve_button_calls_api
test_admin_kb_review_reject_button_calls_api
test_admin_kb_two_reviewer_constraint_shown_in_ui   // approve button disabled if same reviewer already
test_admin_audit_log_renders_timestamp_and_action
test_admin_audit_log_filter_by_user
test_admin_access_denied_for_clinic_hcp
```

### Gate
```bash
cd frontend && npm run typecheck && npm run test -- --run
# All frontend tests: 0 failures, 0 type errors
```

---

## Phase E0 — E2E Scaffold

### Goal
Playwright configured in `frontend/e2e/`.  
Backend runs in test mode (SQLite in-memory seeded with fixture data).  
One smoke test confirms the app loads.

### New files
- `frontend/e2e/playwright.config.ts`
- `frontend/e2e/fixtures.ts` — seed data helpers
- `frontend/e2e/smoke.spec.ts`

### Tests
```typescript
// smoke.spec.ts
test_app_loads_without_js_errors
test_login_page_visible_when_unauthenticated
```

### Gate
```bash
npx playwright test --project=chromium e2e/smoke.spec.ts
```

---

## Phase E1 — Critical Path E2E

### Goal
End-to-end tests for the paths a clinic HCP and care coordinator take every day.

### Tests — `frontend/e2e/critical-path.spec.ts`

```typescript
// Auth
e2e_login_redirects_to_patient_list_after_jwt_set

// Patient list
e2e_patient_list_shows_correct_counts
e2e_patient_list_tab_filtering_works
e2e_reminder_dots_visible_for_patient_with_alerts

// Patient detail
e2e_navigate_to_patient_detail_from_list
e2e_timeline_events_visible_in_order
e2e_add_doctor_note_appears_in_timeline
e2e_acknowledge_reminder_removes_it_from_active_list
e2e_consultation_send_and_reply_full_cycle

// OpenOnco (doctor-initiated)
e2e_onco_button_click_loads_analysis_page
e2e_onco_analysis_shows_treatment_tracks
e2e_onco_select_track_creates_plan

// MTD
e2e_add_patient_to_mtd_session
e2e_coordinator_writes_mtd_conclusion
e2e_conclusion_appears_in_patient_timeline

// Drug requisition
e2e_drug_reminder_to_submission_full_cycle
```

### Gate
```bash
npx playwright test --project=chromium e2e/critical-path.spec.ts
```

---

## Phase H0 — Security Hardening

### Goal
Rate limiting, CSP headers, input sanitisation audit, SQL injection test, auth edge cases.

### New files
- `hospital/middleware/security_headers.py`
- `tests/hospital/test_security.py`

### Tests — `tests/hospital/test_security.py`

```python
# --- auth edge cases ---
test_expired_jwt_returns_401
test_tampered_jwt_signature_returns_401
test_missing_jwt_returns_401
test_wrong_role_returns_403
test_pending_role_blocked_from_all_write_endpoints

# --- input validation ---
test_mrn_with_sql_injection_returns_422_or_safe_query   # param binding prevents injection
test_mrn_with_xss_payload_stored_and_returned_escaped
test_body_with_oversized_string_returns_413_or_422

# --- headers ---
test_response_has_x_content_type_options_header
test_response_has_x_frame_options_header
test_api_response_has_no_server_header_leaking_version
test_cors_rejects_unlisted_origin

# --- rate limiting ---
test_login_endpoint_rate_limited_after_20_requests
test_his_webhook_rate_limited_after_100_requests

# --- audit completeness ---
test_every_patient_read_produces_audit_log_row
test_every_plan_generation_produces_audit_log_row
test_every_annotation_produces_audit_log_row
test_cross_doctor_access_audit_log_has_mrn_hash      # mrn_hash not raw MRN
test_audit_log_is_append_only                        # DELETE on audit_log returns 405

# --- PHI in logs ---
test_mrn_not_logged_in_plaintext                     # audit_log.mrn_hash != raw mrn
test_patient_name_not_in_audit_log
```

### Final gate (all suites)
```bash
pytest tests/hospital/ --asyncio-mode=auto -x -q                           # all backend
cd frontend && npm run typecheck && npm run test -- --run                   # all frontend unit
npx playwright test --project=chromium                                      # all E2E
echo "ALL GATES GREEN — ready for pilot deployment"
```

---

## Branch strategy

Each phase runs on its own branch:

```
feat/b0-schema-expansion
feat/b1-patient-registry
feat/b2-timeline-events
feat/b3-his-adapter
feat/b4-reminder-engine
feat/b5-consultations
feat/b6-mtd
feat/b7-push-notifications
feat/b8-onco-enhancement
feat/f0-react-scaffold
feat/f1-auth-flow
feat/f2-patient-list
feat/f3-patient-detail
feat/f4-board
feat/f5-onco-analysis
feat/f6-drug-req
feat/f7-admin
feat/e0-e2e-scaffold
feat/e1-critical-path-e2e
feat/h0-security-hardening
```

Merge to `main` only after the phase gate command exits 0 and at least one human review.  
Two-reviewer rule (CHARTER §6.1) applies to any merge that touches `knowledge_base/hosted/content/`.

---

## What this plan does NOT include

- OpenOnco knowledge base and engine expansion (separate workstream)
- HIS crawler implementation (separate repo)
- Compute tools (separate repo, adapter already stubbed)
- Multi-tenancy / multi-hospital
- FHIR-native patient import
- Real-time collaboration (WebSocket)
- SAML/LDAP SSO integration (post-pilot)
