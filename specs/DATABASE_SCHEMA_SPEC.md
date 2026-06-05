# Database Schema Specification

**Version:** 0.1 draft  
**Status:** pending review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Overview

PostgreSQL 16 (production) / SQLite (MVP pilot).  
ORM: SQLAlchemy 2.x async.  Migrations: Alembic.

**PHI policy (CHARTER §9.3):**
- `mrn` stored only in `cases` + `plans` tables (encrypted at rest via
  PostgreSQL column encryption or application-level AES-256-GCM).
- Audit log uses `mrn_hash` (SHA-256 + hospital salt) — never plaintext MRN.
- `plan_json` contains patient findings/biomarkers; encrypted at rest.
- No patient data in `kb_reviews` or `audit_log.diff_summary`.

---

## 2  Tables

### 2.1  `cases`

One row per patient case.  Links MRN to OpenOnco disease model.

```sql
CREATE TABLE cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mrn             TEXT NOT NULL UNIQUE,   -- encrypted in prod
    disease_id      TEXT NOT NULL,          -- e.g. "DIS-BREAST"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_plan_id    TEXT,                   -- FK → plans.plan_id (denorm)
    created_by      TEXT NOT NULL,          -- user_id from JWT
    fhir_patient_id TEXT                    -- future CMS linkage (nullable)
);
CREATE INDEX idx_cases_disease ON cases(disease_id);
```

---

### 2.2  `plans`

One row per plan version.  `plan_json` = `PlanResult.to_dict()`.

```sql
CREATE TABLE plans (
    plan_id         TEXT PRIMARY KEY,       -- from PlanResult.plan.id
    mrn             TEXT NOT NULL,          -- encrypted in prod
    version         INTEGER NOT NULL DEFAULT 1,
    plan_json       JSONB NOT NULL,         -- encrypted in prod
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT NOT NULL,
    supersedes      TEXT REFERENCES plans(plan_id),
    superseded_by   TEXT REFERENCES plans(plan_id),
    revision_trigger TEXT,                  -- why this version was created
    selected_track_id TEXT,                -- track chosen by clinician (set on annotation)
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','active','superseded','rejected'))
);
CREATE INDEX idx_plans_mrn ON plans(mrn);
CREATE INDEX idx_plans_status ON plans(status);
```

---

### 2.3  `annotations`

Append-only clinician commentary on a plan.  No UPDATE, no DELETE.

```sql
CREATE TABLE annotations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         TEXT NOT NULL REFERENCES plans(plan_id),
    user_id         TEXT NOT NULL,
    user_role       TEXT NOT NULL,          -- clinical role at time of annotation
    annotation_type TEXT NOT NULL
                    CHECK (annotation_type IN
                           ('approve','comment','flag','reject','select_track')),
    text            TEXT,
    track_id        TEXT,                   -- set when annotation_type='select_track'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_annotations_plan ON annotations(plan_id);
-- Row-level trigger: prevent UPDATE/DELETE
```

---

### 2.4  `drug_requisitions`

Tracks generated drug requisitions and their submission status.

```sql
CREATE TABLE drug_requisitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         TEXT NOT NULL REFERENCES plans(plan_id),
    mrn             TEXT NOT NULL,          -- encrypted in prod
    track_id        TEXT NOT NULL,
    requisition_json JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','submitted','approved','rejected')),
    submitted_at    TIMESTAMPTZ,
    external_ref    TEXT                    -- DAS system ref number (future)
);
CREATE INDEX idx_dreq_plan ON drug_requisitions(plan_id);
```

---

### 2.5  `audit_log`

Immutable append-only event log.  Never contains plaintext MRN or PHI.

```sql
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         TEXT NOT NULL,
    action          TEXT NOT NULL,
    -- action values: plan.generate | plan.revise | annotation.add |
    --   drug_req.create | drug_req.submit | patient_link.create |
    --   kb.review.approve | kb.review.reject | case.create
    resource_type   TEXT,                   -- 'plan', 'annotation', 'drug_req', etc.
    resource_id     TEXT,
    mrn_hash        TEXT,                   -- SHA-256(mrn + AUDIT_SALT)
    diff_summary    TEXT,                   -- human-readable change summary (no PHI)
    ip_address      INET,
    user_agent      TEXT
);
CREATE INDEX idx_audit_ts ON audit_log(ts DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_mrn_hash ON audit_log(mrn_hash);
-- No UPDATE, no DELETE trigger
```

---

### 2.6  `kb_reviews`

Tracks pending two-reviewer approvals for KB entity changes (CHARTER §6.1).

```sql
CREATE TABLE kb_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     TEXT NOT NULL,          -- 'indication', 'regimen', 'redflag', etc.
    entity_id       TEXT NOT NULL,
    branch_name     TEXT,                   -- git branch carrying the change
    pr_number       INTEGER,                -- GitHub PR number
    diff_summary    TEXT NOT NULL,
    submitted_by    TEXT NOT NULL,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewer_1      TEXT,
    reviewer_1_at   TIMESTAMPTZ,
    reviewer_2      TEXT,
    reviewer_2_at   TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected','withdrawn')),
    closed_at       TIMESTAMPTZ,
    CONSTRAINT two_distinct_reviewers CHECK (
        reviewer_1 IS NULL OR reviewer_2 IS NULL OR reviewer_1 <> reviewer_2
    )
);
CREATE INDEX idx_kbrev_status ON kb_reviews(status);
CREATE INDEX idx_kbrev_entity ON kb_reviews(entity_type, entity_id);
```

---

### 2.7  `users` (MVP only — replaced by SSO in prod)

```sql
CREATE TABLE users (
    user_id         TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL
                    CHECK (role IN (
                        'tumor_board_hcp','clinic_hcp','patient',
                        'kb_admin','auditor'
                    )),
    password_hash   TEXT NOT NULL,          -- bcrypt
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active          BOOLEAN NOT NULL DEFAULT TRUE
);
```

---

## 3  Alembic migration structure

```
alembic/
├── env.py
├── script.py.mako
└── versions/
    └── 0001_initial_schema.py    ← creates all tables above
```

Run: `alembic upgrade head`

---

## 4  Encryption at rest

In production, `mrn` and `plan_json` columns use application-level
encryption before INSERT (not relying solely on disk encryption):

```python
from cryptography.fernet import Fernet

FERNET_KEY = os.environ["DB_ENCRYPTION_KEY"]   # 32-byte base64 key
_fernet = Fernet(FERNET_KEY)

def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()
```

`plan_json` is encrypted as a JSON string (Fernet → stored as TEXT, not
JSONB in encrypted mode — lose indexability; acceptable for MVP).

---

## 5  audit_log MRN hashing

```python
import hashlib, os

AUDIT_SALT = os.environ["AUDIT_MRN_SALT"]   # 32 random bytes, hex-encoded

def hash_mrn(mrn: str) -> str:
    return hashlib.sha256(
        (mrn + AUDIT_SALT).encode()
    ).hexdigest()
```

The salt is stored only in environment config, never in the database.
Without the salt, `mrn_hash` cannot be reversed to find the MRN.

---

## 6  Retention policy

| Table | Retention | Rationale |
|-------|-----------|-----------|
| `cases` | Indefinite | Patient record reference |
| `plans` | Indefinite | Audit trail for clinical decisions |
| `annotations` | Indefinite | Append-only, part of clinical record |
| `drug_requisitions` | 10 years | Hospital pharmacy record requirement |
| `audit_log` | 10 years | Regulatory / accreditation |
| `kb_reviews` | Indefinite | Clinical governance record |
| `users` (MVP) | Until SSO migration | Delete on SSO cutover |

---

## 7  SQLite compatibility (MVP)

All DDL above is compatible with SQLite except:
- `UUID` → use `TEXT` (SQLAlchemy handles transparently)
- `JSONB` → use `JSON` (SQLAlchemy handles transparently)
- `gen_random_uuid()` → use `uuid.uuid4()` at application layer
- `INET` → use `TEXT`
- Row-level triggers for append-only → enforced at application layer instead

SQLAlchemy model annotations handle this transparently via
`TypeDecorator`.  No separate SQLite migration needed.
