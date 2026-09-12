# CHANGELOG

All notable changes to OpenOnco. Format roughly based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning per CHARTER §5 (KB content cadence).

---

## [Unreleased]

---

## [0.1.0] — 2026-06-05

### Hospital Edition — initial release (phases B0–H0)

#### Backend (`hospital/`)
- Patient registry with care-team, HIS sync badge, pagination + full-text search
- Timeline API (doctor notes, system events, `onco_query_initiated`)
- OpenOnco KB integration: `POST /plan`, `GET /plan/{id}`, `/plan/gaps` (two-pass gap finder)
- Reminder engine: rule-based reminders (drug reapplication, BRCA follow-up, mammography, etc.), acknowledge endpoint, daily scheduler
- MTD (tumor board) sessions + cases: create, add case, conclude, annotation timeline
- Consultations: create, messages, close; care-team authorization on read
- Drug requisition: create from plan track, status PATCH, HTML preview/print
- HIS webhook: HMAC-SHA256 auth, idempotency key, sync-event ingestion
- KB admin: status, refresh, crawler-notify webhook
- Audit log: structured action log for all clinical writes
- Push notifications: VAPID / Web Push per-user subscription
- Google OAuth 2.0 + JWT session (HttpOnly cookie)
- Role-based access: `tumor_board_hcp`, `clinic_hcp`, `kb_admin`, `auditor`, `pending`
- Rate limiting (slowapi), CORS, body-size limit, security headers
- Alembic migrations (initial schema v0.1)

#### Frontend (`frontend/`)
- React 18 + TypeScript PWA (Vite, service worker, offline shell)
- Patient list: search, tabs (all / follow-up / consulted / MTD / alerts), pagination, HIS badge
- Patient detail: timeline, reminders (acknowledge), care-team, consultations, MTD button, drug-req link
- Tumor board (BoardPage): session list, expand-to-plan tracks, conclude, annotation notes, export agenda
- Drug requisition wizard: async plan load, track select, submit, print preview
- Clinic page: appointment-based patient workflow
- Admin page: KB status panel, entity counts, refresh button, user management
- Auth flow: Google OAuth redirect, pending-state gate

#### Knowledge base
- CHARTER §8.3 rule engine (`knowledge_base/engine/`): deterministic, version-controlled YAML
- 78 diseases, 438 biomarker actionability, 173 biomarkers, 383 sources, 251 drugs, 424 indications, 474 redflags, 360 regimens, 140 algorithms
- CIViC (CC0) as primary actionability source; OncoKB rejected per ToS conflict (see `docs/reviews/`)
- Schema validation CI (Python 3.12, `scripts/audit_validator.py`)

#### Infrastructure
- GitHub Actions CI: `validate` (KB schema), `backend` (pytest 282 tests), `frontend` (Vitest + tsc)
- `Dockerfile` multi-stage (Node 20 frontend build → Python 3.11 backend)
- `docker-compose.yml` with SQLite (dev) and PostgreSQL profile (prod)
- `.env.example` with all required variables documented

#### Security fixes (from code review)
- Consultations and reminders endpoints now gated behind care-team membership
- Annotation `user_role` derived from JWT, not client body
- `revise_plan` validates and marks old plan `superseded`; `get_plan` surfaces stale-plan warning
- `revision_trigger` null guard; gap probe failures now logged instead of silently dropped
- Drug requisition: fix wrong `name_ua` key for Chinese regimen name field

### OncoKB integration — Phases 0 (mock) / 1a / 2 / 3a / 3b / 4 / 4.1 + 4 follow-ups

**Status:** code-complete to `master`; **production deploy gated** on
real OncoKB Academic-tier token + GCP credentials (Phase 1b operational
gate). Engine is ready to run with `--oncokb-proxy=URL` against a live
or mocked proxy as soon as Phase 1b lands.

Authoritative plan: `docs/plans/archive/oncokb_integration_safe_rollout_v3.md`
(18 sections, 12-item threat model, 20+ acceptance criteria, all 8
clinical questions resolved).

---

#### Architecture (CHARTER §8.3 surface-only invariant)

- New module `knowledge_base/engine/oncokb_client.py` — `OncoKBClient`
  Protocol with three implementations: `NullOncoKBClient` (default —
  returns disabled-error per query), `StubOncoKBClient` (fixture-driven
  for tests, no I/O), `HttpxOncoKBClient` (sync httpx → proxy;
  per-query try/except mapping all errors to `OncoKBError` instead of
  raising).
- New module `knowledge_base/engine/oncokb_conflict.py` —
  `detect_resistance_conflicts(tracks, oncokb_results)`. Pure function;
  detects when an engine-recommended drug appears in OncoKB R1/R2
  evidence for one of the patient's biomarkers. T3 mitigation per
  CHARTER §15.2 C6 (automation-bias guard).
- New module `knowledge_base/engine/oncokb_extract.py` — variant
  normalization + extractor. Pure: `normalize_variant(raw, gene)`
  conservative — when uncertain, SKIP (never guess).
- New module `knowledge_base/engine/oncokb_types.py` — dataclasses
  (`NormalizedVariant`, `OncoKBQuery`, `OncoKBTherapeuticOption`,
  `OncoKBResult`, `OncoKBError`, `ResistanceConflict`, `OncoKBLayer`)
  + frozensets (`SURFACED_LEVELS = {3A, 3B, 4, R1, R2}` per locked Q1).
- New module `knowledge_base/engine/oncotree_fallback.py` — three-tier
  resolver (explicit `Disease.oncotree_code` → ICD-10 family fallback
  → pan-tumor) with C00–D49 mapping table.
- `knowledge_base/engine/plan.py` — `generate_plan()` gains
  `oncokb_enabled=False` (default OFF) + `oncokb_client=None` kwargs.
  Wiring runs AFTER tracks/actionability are final — surface-only.
  Wrapped in try/except per fail-open contract: OncoKB outage never
  blocks Plan generation.
- `knowledge_base/engine/render_oncokb.py` — HCP-only OncoKB section +
  inline R1/R2 banners + ONCOKB_CSS palette intentionally distinct
  from engine track palette (CHARTER §15.2 C6).
- `knowledge_base/engine/render.py` — section inserted between
  `_render_what_not_to_do` and `_render_monitoring_phases` (after
  supportive-care, before monitoring per safe-rollout v3 §4.1);
  inline track-card banner injected into each track loop.
- `knowledge_base/engine/cli.py` — `--oncokb-proxy URL` +
  `--oncokb-timeout SECONDS` flags; both default-OFF.
  `revise_plan()` re-queries OncoKB on revision per locked Q7.

#### Schema additions

- `Disease.oncotree_code: Optional[str]` (canonical MSK OncoTree code).
- `Biomarker.oncokb_lookup: Optional[OncoKBLookupHint]` — opt-in hint
  (gene + variant). Conservative: biomarkers without a hint are
  SKIPPED (never guessed) by the variant extractor.
- `OncoKBLookupHint`, plus extension fields `oncokb_skip_reason`,
  `external_ids` for downstream tooling.
- `PlanResult.oncokb_layer: Optional[OncoKBLayer]`.
- `provenance.EventType += "external_kb_consulted",
  "resistance_conflict_detected"`; `TargetType += "oncokb_query"`
  (backward-compatible Literal extension).

All schema additions are Optional / additive — existing entities load
unchanged. No migration required.

#### Proxy hardening (`services/oncokb_proxy/`)

Phase 1a hardening before Phase 1b deploy:

- openonco.info added to default CORS (was .org only).
- slowapi rate-limit (60/min per-IP default; `ONCOKB_RATE_LIMIT_DISABLED=1`
  skips for tests; tightenable via `ONCOKB_RATE_LIMIT` env var).
- X-Request-Id middleware — echo client header or mint `req-{12hex}`.
- Structured JSON access log via custom Formatter — emits
  request_id/method/path/status/latency_ms; **no token, no body**.
- Token-scrub regex strips Bearer/api-key/token from any error body
  and log line; idempotent; applied to upstream error echo + the
  catch-all 502 wrapper.
- Master kill-switch `ONCOKB_INTEGRATION_ENABLED=0` → `/lookup` returns
  503 fast (healthz still works for diagnosis); per safe-rollout v3
  §18 disaster-recovery runbook.
- `/healthz` reports `git_sha` + `integration_enabled` + `rate_limit` state.

#### KB content additions (PR-B + PR-C)

- **65/65 Diseases** populated with `oncotree_code` (PR-B). Mapping
  table preserved in `scripts/populate_oncotree_codes.py`.
- **20 Biomarkers** with `oncokb_lookup` hints (PR-C):
  - **Pre-existing** (8): BIO-BRAF-V600E, BIO-MYD88-L265P, BIO-KRAS-G12C,
    BIO-RHOA-G17V, BIO-EZH2-Y641 (Y641F), BIO-FLT3-D835 (D835Y),
    BIO-JAK2 (V617F), BIO-NPM1 (W288fs).
  - **New variant-specific** (12): BIO-EGFR-L858R / T790M / EXON19-DELETION /
    EXON20-INSERTION, BIO-KRAS-G12D / G12V, BIO-NRAS-Q61R, BIO-BRAF-V600K,
    BIO-PIK3CA-H1047R, BIO-KIT-D816V, BIO-RET-M918T, BIO-IDH1-R132H.
  - Each new entity carries full schema (id, names UA+EN, biomarker_type,
    mutation_details, oncokb_lookup hint, sources cited from NCCN/ESMO
    2024-2025, notes with 1L therapy rationale + alternate variants).

#### Locked clinical decisions (Q1–Q8)

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | Show only Levels **3A/3B/4 + R1/R2**. Filter Levels 1/2. | Engine already covers Levels 1/2 in its tracks; surfacing them = noise + automation-bias risk. |
| Q2 | R1 + R2 **both inline** in track-card. R1 = red 🛑, R2 = amber ⚠. Both also in OncoKB section "Resistance" block. | Overshow > hide for safety (§15.2 C6). |
| Q3 | Top 3 visible; rest in `<details>` "Показати ще N". | Density vs completeness balance. |
| Q4 | Pan-tumor fallback shown with warning badge. | Better than silently hiding evidence. |
| Q5 | Multiple biomarkers → single combined table + cross-biomarker analysis (drug-overlap detection). | One mental model + integration-layer-unique value. |
| Q6 | PMID inline as clickable PubMed links `target=_blank rel=noopener`. | Lower verification friction. |
| Q7 | revise_plan re-queries OncoKB on every revision. | Data may have updated; staleness defeats integration value. |
| Q8 | Confidence: `Level 3A · 5 PMIDs · FDA-approved (sotorasib, 2021)`. | Quality signal beyond level alone. |

#### Phase 0 — mock-mode evidence

Phase 0 documented as 🟡 **PROVISIONAL** in
`docs/plans/archive/oncokb_api_evidence.md`. Verified from public docs
(api.oncokb.org, faq.oncokb.org, oncokb-annotator):

- A1 endpoint `/annotate/mutations/byProteinChange` ✓
- A2 `Authorization: Bearer {token}` ✓
- A3 `LEVEL_X` format on `treatments[].level` ✓
- A4 top-level `dataVersion` field ✓
- A6 short HGVS-p (`V600E`) accepted ✓
- A7 `tumorType` (camelCase) param ✓
- A8 separate endpoints for structural variants + CNAs ✓
  (validates MVP scope decision)
- A10 token expires every 6 months with auto-renewal email ✓
- A11 PMIDs as flat string array ✓

**Critical discovery (A3-bis):** `treatments[].fdaApproved` field
**DOES NOT EXIST** in OncoKB response. Q8 FDA badge therefore sources
truth from our own `Drug.regulatory_status.fda` instead of from OncoKB
(implemented as Phase 4.1, see below).

**Provisional fixtures:** 12 synthesized response JSONs at
`tests/fixtures/oncokb_responses/`. Each carries `_provisional: true`
flag — refused to be silently treated as verified. Replace with
real-token curl captures during Phase 1b operational gate. Generator
script preserved (`scripts/_generate_oncokb_fixtures.py`).

**Undocumented (defer to production discovery):**
- A5 quota — will know at first 429
- A9 rate-limit headers — same

#### Phase 4.1 — FDA badge sources from Drug entity

Per A3-bis discovery:

- New public helper `render_oncokb.build_fda_index(drugs_lookup)` —
  builds `{lowercase_drug_name: (approved, year)}` from
  `kb_resolved.drugs`. Indexes preferred + english + ukrainian +
  synonyms + brand_names per Drug for case-insensitive match against
  OncoKB's drug names.
- `_format_fda_badge` + `_format_confidence` use the index.
  Conservative: silent badge on no-match OR not-approved (honest
  "we don't know", not "not approved").
- `render_oncokb_section(layer, *, mode, target_lang, drugs_lookup=None)`
  — new optional kwarg; backward-compat (None → no badges, but section
  still renders normally).
- `render.py` wires `plan_result.kb_resolved.drugs` → render call.

#### Coverage report (CI gate)

`scripts/oncokb_coverage_report.py` — observability for the
integration. For each Disease reports tier-1 explicit OncoTree code,
tier-2 fallback resolution, final code + pan-tumor warning flag,
biomarker reference count + how many have oncokb_lookup hint.

CLI flags: `--json` (structured output), `--warn` (exit 2 if any
Disease falls to tier-3 pan-tumor — intended for CI as soft gate;
not a build blocker).

Current state on this commit: 65/65 diseases tier-1 (100%); 0
pan-tumor warnings; 91 biomarker references across all indications
with ~20 hints providing real coverage of actionable variants.

#### Tests

**202 OncoKB-specific tests green:**

| Suite | Count | Locks |
|-------|-------|-------|
| Phase 1a proxy hardening | 20 | rate-limit / scrub / kill-switch / X-Request-Id |
| Phase 3a variant normalize | 64 | 30+ canonical input forms; HGVS-c always-skip; idempotency |
| Phase 3b engine wiring + invariants | 18 | AC-1/2/7/9/15/16: import-graph firewall, fail-open, default-OFF, resistance detection |
| Phase 4 + 4.1 render | 30 | AC-3/8/16/17/19/20: patient-mode regex grep, attribution position, Levels 1/2 absent, cross-biomarker overlap, PMID PubMed links, FDA-from-Drug-entity |
| Follow-up #2 OncoTree fallback | 41 | C00–D49 mappings; 3-tier chain; integration test against real KB |
| Follow-up #3 coverage report | 3 | Smoke tests for text/JSON/--warn modes |
| Follow-up #4 CLI | 5 | --oncokb-proxy flag wiring, source-grep AC-7 preservation |
| Mock-mode Phase 0 contracts | 41 | 3 shape-suites × 12 fixtures + 5 e2e via mocked HttpxOncoKBClient + 1 provisional-marker guard |

#### Plan documents

- `docs/plans/archive/oncokb_integration_safe_rollout_v3.md` — authoritative
  18-section plan with threat model, locked Q1–Q8, 6 phases, 20 ACs,
  hard-pause gates at 1b/5d/5e.
- `docs/plans/archive/oncokb_api_evidence.md` — 🟡 PROVISIONAL A1–A11
  registry; flips to ✅ VERIFIED only after real-token curl pass.
- `docs/plans/archive/oncokb_data_scope.md`, `oncokb_cache_strategy.md`,
  `oncokb_render_integration.md`, `oncokb_source_classification.md`
  — older decision-records, subordinate to v3.

#### Remaining gates (not code — operational)

- **Phase 0 verify (real curl):** needs OncoKB Academic-tier token to
  promote evidence doc 🟡 → ✅. Will also replace 12 provisional
  fixtures with real captures. Script for capture procedure documented
  in `oncokb_api_evidence.md`.
- **Phase 1b deploy:** needs user OK + GCP credentials. Token in
  Secret Manager, Cloud Run service `--no-allow-unauthenticated`,
  `--max-instances=3`, custom domain `oncokb-proxy.openonco.info`.
  Operational runbook entry for 6-month token rotation cycle staged.
- **Phase 5b/d/e rollout:** calendar-gated soak periods. Each has
  rollback documented as one-command revert.

CHARTER §6.1 dev-mode signoff exemption (project_charter_dev_mode_exemptions)
applies for v0.1 phase — all OncoKB clinical content commits stay STUB
(`reviewer_signoffs: 0`) per condition.

---

## Earlier history

Pre-changelog. See `git log` and `docs/plans/` for prior workstreams
(rule engine + render + MDT orchestrator + diagnostic mode + reference
case + KB expansion to 50+ diseases / 137+ drugs / etc.).
