# Hospital System Specification

**Version:** 0.1 draft  
**Status:** pending review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Purpose

OpenOnco Hospital Edition is a **standalone clinical decision support
add-on** deployed within a hospital intranet.  It wraps the existing
OpenOnco rule engine + knowledge base into a multi-role web portal for:

- Tumor board pre-meeting preparation (`/board`)
- Outpatient HCP + patient-facing output (`/clinic`, `/patient`)
- Knowledge base governance + audit (`/admin`)

The system does **not** replace existing hospital systems (CMS, DAS,
HIS).  Integration adapters (`knowledge_base/integrations/`) exist for
future connectivity but are out of scope for v1.

CHARTER §8.3 applies throughout: **the rule engine makes clinical
recommendations, not LLMs.**  LLMs only structure free text and
translate output.

---

## 2  Deployment topology

```
Hospital intranet
┌──────────────────────────────────────────────────────┐
│                                                      │
│   Browser (HCP / Patient)                            │
│       │  HTTPS                                       │
│       ▼                                              │
│   Reverse proxy / hospital SSO gateway               │
│   (nginx + hospital LDAP / AD / SAML)                │
│       │  JWT with role claim                         │
│       ▼                                              │
│   FastAPI app  (Python 3.12)                         │
│   ├── /api/v1/*        REST endpoints                │
│   ├── /board           Tumor board portal            │
│   ├── /clinic          Outpatient portal             │
│   ├── /patient         Patient-facing view           │
│   └── /admin           KB + audit dashboard          │
│       │                                              │
│       ├── knowledge_base.engine   (in-process)       │
│       ├── PostgreSQL              (patient data)     │
│       └── knowledge_base/hosted/content   (KB YAML)  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

MVP alternative: SQLite instead of PostgreSQL for single-server pilot.
Switch is a one-line config change (SQLAlchemy URL).

---

## 3  Role model

| Role ID | Display name | Portal access | Clinical write |
|---------|-------------|---------------|----------------|
| `tumor_board_hcp` | Tumor Board HCP | /board, /admin/cases | Add annotations |
| `clinic_hcp` | Clinic HCP | /clinic, /patient | Generate plans, add annotations |
| `patient` | Patient | /patient (own plan only) | None |
| `kb_admin` | KB Administrator | /admin/kb | Approve KB entities |
| `auditor` | Clinical Auditor | /admin/cases, /admin/audit | Read-only |

Roles are asserted in the hospital SSO JWT claim `openonco_role`.  
For MVP without SSO: roles stored in a local `users` table; login via
username + bcrypt password.

---

## 4  Core data flow

```
1. HCP enters patient data
   │  (structured form OR free-text → LLM extraction)
   ▼
2. FastAPI validates + calls generate_plan(patient_dict)
   │  engine reads KB YAML, runs decision tree
   ▼
3. PlanResult persisted to plans table (patient_id, plan_json)
   │
   ├── 4a. /board renders full clinical HTML (render_plan_html mode=clinician)
   ├── 4b. /clinic renders split HCP + patient HTML (mode=both)
   └── 4c. /patient renders patient-only HTML (mode=patient)

5. Clinician adds annotation (approve / comment / flag)
   → stored in annotations table, append-only

6. Optional: export DrugRequisition JSON for later DAS integration
```

---

## 5  Technology stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend framework | FastAPI 0.115+ | Async, typed, auto-docs; same Python 3.12 as engine |
| ASGI server | Uvicorn + Gunicorn | Production-grade |
| ORM / DB | SQLAlchemy 2.x + Alembic | Type-safe, migration support |
| DB (prod) | PostgreSQL 16 | Multi-user, JSON column for plan_json |
| DB (MVP) | SQLite | Zero-config single-server pilot |
| Frontend | Server-side HTML (Jinja2) + HTMX | Minimal JS; works on hospital IE-era proxies |
| Auth (MVP) | Local JWT (python-jose) | No SSO dependency for pilot |
| Auth (prod) | Hospital LDAP / SAML 2.0 | Via python3-saml / authlib |
| LLM client | Anthropic SDK (claude-sonnet-4-6) | Free-text extraction only (§8.3) |
| Container | Docker + docker-compose | Single `docker compose up` for pilot |

---

## 6  Configuration

All config via environment variables (`.env` file or docker secrets):

```ini
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/openonco

# KB path (mounted volume in docker)
KB_ROOT=/app/knowledge_base/hosted/content

# LLM (extraction only — CHARTER §8.3)
ANTHROPIC_API_KEY=sk-ant-...
EXTRACTION_MODEL=claude-sonnet-4-6

# Auth (MVP)
JWT_SECRET=...
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# Hospital SSO (prod — leave blank for MVP)
SAML_IDP_METADATA_URL=
LDAP_URL=

# Patient plan persistence
PATIENT_PLANS_DIR=/data/patient_plans
```

---

## 7  Security requirements

| Requirement | Implementation |
|-------------|---------------|
| No PHI in git (CHARTER §9.3) | patient_plans/ gitignored; DB outside repo |
| Audit trail | Every plan generation + annotation logged to audit_log |
| Role enforcement | FastAPI dependency `require_role(["tumor_board_hcp"])` on each endpoint |
| Plan data at rest | PostgreSQL with filesystem encryption (hospital policy) |
| Session timeout | JWT exp = 8 hours; /patient tokens = 24 hours (print window) |
| LLM boundary (§8.3) | LLM calls isolated to `/api/v1/extract`; engine calls never pass through LLM |

---

## 8  Phased rollout

| Phase | Scope | Goal |
|-------|-------|------|
| MVP (v0.1) | /board + /clinic + SQLite + local auth | Single-hospital pilot |
| v0.2 | /patient + /admin/kb + PostgreSQL | Multi-HCP, patient QR output |
| v0.3 | /admin/cases + /admin/audit + LDAP SSO | Governance + audit readiness |
| v1.0 | CMS/DAS integration + FHIR push | Full system integration |

---

## 9  Out of scope (v0.1)

- CMS/DAS integration (adapters built but not wired)
- Multi-hospital multi-tenancy
- Real-time collaboration (WebSocket)
- Mobile app
- FHIR-native patient import (use structured form or LLM extraction)
