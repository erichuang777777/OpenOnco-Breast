# Physician-platform review — guideline rules, UI/visualization, audit interface

**Date:** 2026-06-13
**Branch:** `claude/physician-platform-review-614230`
**Scope:** Review of the rule/guideline engine; improvements to the hospital
React UI with guideline-flowchart visualization; a guideline import &
verification (audit) interface.

This document is the written deliverable for task 1 (review) and records the
design of the code shipped on this branch for tasks 2 (UI/visualization) and 3
(audit interface).

---

## 1. Architecture, in one picture

```
 React SPA (frontend/)                  FastAPI (hospital/)              Rule engine (knowledge_base/)
 ─────────────────────                  ──────────────────              ────────────────────────────
 ClinicPage  ──POST /plan──────────────▶ decision/api/plan.py  ─────────▶ engine/plan.generate_plan()
 GuidelinesPage ─GET /guidelines───────▶ decision/api/guidelines.py ────▶ guideline_service (reads YAML)
 AuditPage  ──GET /admin/kb/* ─────────▶ admin/api/kb.py        ─────────▶ admin/services/kb_status.py
                                         (JWT + role guard)               walk_algorithm() → trace
```

Three tiers, cleanly separated:

1. **Knowledge base** — versioned YAML entities under
   `knowledge_base/hosted/content/` (180 algorithms, ~424 indications, ~383
   sources, ~360 regimens, ~474 red flags, …), validated by Pydantic on load.
   Read-only at request time.
2. **Hospital backend** — FastAPI app that authenticates clinicians (Google
   OAuth → JWT cookie), stores patient/timeline/MTD/review state in
   SQLite/Postgres, and brokers every call to the engine through one adapter
   (`decision/services/onco_engine_client.py`). Nothing outside that adapter
   imports `knowledge_base.engine` directly.
3. **React SPA** — role-based portals (clinic HCP, tumor-board HCP, kb_admin,
   auditor), Vite + TypeScript, tested with Vitest + MSW.

The separation is disciplined and is the codebase's biggest strength: the
clinical logic is auditable YAML, the LLM never selects a regimen (CHARTER
§8.3), and the hospital layer is a thin, testable broker.

---

## 2. How a guideline is represented and evaluated

### 2.1 The data model

A clinical guideline is an **`Algorithm`** with a `decision_tree` — an ordered
list of steps. Each step is a node:

```yaml
- step: 3
  evaluate:
    any_of:
      - red_flag: RF-BREAST-TNBC          # fires if the RedFlag's trigger matches
      - {finding: tnbc_status, value: true}
      - {condition: "ER <1% AND PR <1% (TNBC)"}   # prose — see §2.3
  if_true:  { next_step: 4 }
  if_false: { next_step: 5 }
```

Branches resolve to either `result: IND-…` (a terminal **Indication**) or
`next_step: N`. Indications carry the actual clinical payload — recommended
regimen, evidence level, NCCN category, expected outcomes (each citation-bearing),
hard contraindications, and a "do-not-do" list.

`RedFlag` triggers are themselves declarative (`any_of`/`all_of`/`none_of` over
`{finding, value}` or `{finding, threshold, comparator}` clauses), so a step can
compose named clinical signals rather than restating raw findings.

### 2.2 The evaluator and its trace

`knowledge_base/engine/algorithm_eval.py::walk_algorithm()` walks the tree from
step 1, evaluating each step against the patient's flattened findings, following
`if_true`/`if_false`, and stopping at the first `result` (or falling through to
`default_indication`). Conflict resolution is deterministic: when several red
flags fire in one step, `resolve_redflag_conflict()` picks a winner by
`clinical_direction` → `severity` → `priority`.

Critically, the walker emits a **trace** — one record per visited step:

```python
{"step": 3, "outcome": True, "branch": {"next_step": 4},
 "fired_red_flags": ["RF-BREAST-TNBC"], "winner_red_flag": "RF-BREAST-TNBC"}
```

This trace is the substrate for the new visualization: it is the path the engine
actually walked, which we overlay on the static flowchart to explain *why* a
recommendation was reached. Before this work the trace was computed and then
discarded at the API boundary — `PlanResponse` never exposed it.

### 2.3 Risks found in the guideline layer

- **Prose conditions silently evaluate False.** Many steps still carry
  free-text `condition:` clauses ("Stage IV (locally recurrent unresectable or
  distant metastatic)", "ER <1% AND PR <1%"). The evaluator only resolves a
  `condition` if its exact string is a key in the findings dict; otherwise it
  logs `engine.condition.prose_unevaluable` once and returns False. The
  `ALGO-BREAST-1L` walk emits two such warnings today. The red-flag gates
  (`RF-BREAST-TNBC`, `RF-BREAST-STAGE-IV-METASTATIC`) are the real branch
  drivers and the prose clauses are retained "for backward engine
  compatibility" — but they read as if they were load-bearing. **Recommendation:**
  treat any remaining prose `condition` on a primary gate as tech debt; the
  audit dashboard added here is the natural place to surface a per-algorithm
  "unevaluable-condition" count (follow-up).
- **Track filtering is intentionally lenient** — an indication is dropped only
  when patient biomarkers *explicitly* violate `biomarker_requirements_excluded`;
  missing data never drops a track. This is the right safety bias but means the
  UI must make "missing data that would change the answer" visible. The existing
  two-pass gap finder (`compute_gaps`) does this; the flowchart now complements
  it by showing which branch a missing finding controls.
- **Persisted-plan retrieval is incompletely wired.** `ClinicPage` fetches
  `GET /api/v1/plan/{plan_id}`, but no such route exists server-side (only
  `POST /plan`, `/plan/gaps`, `/plan/{id}/revise`). The frontend tests mock it,
  so this gap is invisible in CI. Not changed here (out of scope), but flagged.

---

## 3. UI & visualization (task 2)

### 3.1 What existed

`ClinicPage` rendered two treatment-track cards with an NCCN chip and an
evidence-level line, plus a hardcoded HER2/ER "extracted fields" stub. There was
**no visualization of the guideline logic** — no flowchart, no decision path, and
no charting library in `package.json`. A clinician could see *what* was
recommended but not *why*, and could not inspect the guideline itself.

### 3.2 What shipped

A dependency-free guideline flowchart, served by a new read-only API and
rendered in two places.

- **Backend `guidelines` API** (`hospital/decision/api/guidelines.py`):
  - `GET /api/v1/guidelines?disease=DIS-BREAST` — list algorithms for a disease.
  - `GET /api/v1/guidelines/{algorithm_id}` — a node/edge graph derived from the
    algorithm's `decision_tree`.
  - Backed by `decision/services/guideline_service.py`, which reads a single
    algorithm YAML (deterministic file-naming, glob fallback, LRU-cached) and
    resolves friendly labels — red-flag definitions, indication regimen names,
    NCCN categories — without loading the whole KB. Each decision node carries
    its human-readable conditions, an ANY/ALL match hint, and the red flags it
    references; each terminal carries the indication's regimen/NCCN/evidence.
  - `overlay_trace()` marks the nodes/edges on a given patient's path.
- **`PlanResponse.trace`** — the engine trace is now passed through the API
  (additive, defaults to `[]`).
- **`GuidelineFlowchart` component** (`frontend/src/components/`) — renders the
  graph as a top-down clinical flowchart: each step shows its match conditions
  and its "if met / if not" branches pointing at the next step or a terminal
  indication. When a trace is supplied it highlights the walked path and surfaces
  a "Recommendation reached" banner. No SVG/graph dependency; accessible DOM text.
- **`GuidelinesPage`** (`/guidelines`) — browse algorithms by disease and view
  any flowchart. Available to every authenticated role.
- **`ClinicPage` integration** — after a plan loads, the page fetches the
  flowchart for `plan.algorithm_id` and renders it with `plan.trace` highlighted,
  under a collapsible "決策路徑 · Decision path" section. This directly answers the
  "visualize the result of the guideline flow chart and provide evidence for the
  decision" requirement.

### 3.3 Why HTML, not a graph canvas

The decision trees here are shallow, mostly-linear chains with branch-offs to
terminals. An HTML/CSS flow reads better for clinicians, is responsive and
printable, needs no new dependency (the gate forbids unreviewed deps creeping
in), and is testable by text query. A force-directed canvas would have been more
fragile for no clinical gain.

---

## 4. Guideline import & verification — audit interface (task 3)

### 4.1 What existed

A genuinely rich *backend*: CIViC TSV→YAML loader with a monthly-refresh CI
workflow, a comprehensive validator (`knowledge_base/validation/loader.py`),
~14 audit scripts (`scripts/audit_*.py`), a `KbReview` table + two-reviewer API
(`PATCH /api/v1/admin/kb/reviews/{id}` enforcing CHARTER §6.1's distinct-reviewer
rule), and an audit log. But **no interactive interface** — reviewers had CLI
scripts, JSON/Markdown reports, and GitHub PR descriptions. The one stub in
`AdminPage` even called `POST …/approve` / `…/reject` routes that don't exist on
the backend (the real route is the `PATCH` with an `action` body).

### 4.2 What shipped

- **Backend `GET /api/v1/admin/kb/ingestion-status`** (`admin/api/kb.py` +
  `admin/services/kb_status.py`) — a read-only verification snapshot:
  - content counts per entity type and a total;
  - CIViC snapshot inventory + freshness (age in days, stale past the
    SOURCE_INGESTION_SPEC §9 six-month window);
  - source-citation staleness (fresh / stale / undated buckets from each
    source's `last_verified`/`current_as_of`, plus the 25 stalest);
  - the review-queue summary (pending / approved / rejected / awaiting-second-
    reviewer), read live from `KbReview`.
  - Visible to `kb_admin` and `auditor`; cached per (kb_root, calendar day).
- **`AuditPage`** (`/audit`) — the interface:
  - **Ingestion status** panel: stat cards (entities, algorithms, indications,
    sources, stale sources, pending reviews), CIViC snapshot line with a stale
    badge, and an expandable stalest-sources list — the visual form of "sources
    older than 6 months enter the audit queue."
  - **Verification queue** panel: each `KbReview` with its entity, PR number,
    diff summary, and 0/2-or-1/2 sign-off state, with Approve / Request-changes /
    Reject wired to the **correct** `PATCH` endpoint. The first reviewer's own
    Approve button is disabled to enforce the two-distinct-reviewer rule in the
    UI as well as the DB.
  - **Auditor read-only mode**: auditors see the queue but get no action buttons.
  - A link into the guideline flowchart browser for visual verification of an
    imported algorithm.

This closes the loop the SPEC describes — import (CIViC/MOZ loaders) → validate
(loader) → **review/verify (now a UI)** → merge (two-reviewer) — for the human in
the middle.

---

## 5. Tests & gates

All additive, all green on this branch:

- Backend: `pytest tests/hospital/` → **283 passed** (13 new across
  `test_api_guidelines.py` and `test_api_kb_status.py`).
- Frontend: `npm run typecheck` clean; `npm run test -- --run` → **137 passed**
  (10 new across `guideline-flowchart`, `guidelines-page`, `audit-page`);
  `npm run build` succeeds.
- No knowledge-base YAML was modified, so the KB validator state is unchanged and
  no clinical content gates are triggered.

The new backend endpoints were verified against the real KB (e.g. the
`ALGO-BREAST-1L` graph resolves 7 decision steps and 9 indication terminals with
regimen names, and the trace overlay correctly highlights a TNBC-metastatic
patient's path to pembrolizumab + chemotherapy).

---

## 6. Recommended next steps (not in this change)

1. **Add `GET /api/v1/plan/{plan_id}`** with persistence so `ClinicPage` shows a
   real saved plan (and a real trace) instead of a mocked one.
2. **Promote prose `condition` gates to red-flag/threshold clauses** and surface
   a per-algorithm unevaluable-condition count on the audit dashboard.
3. **Patient-mode React view** — the engine already renders a patient-mode HTML
   bundle (`render.py`); the SPA has no patient route yet. The flowchart
   component could drive a simplified "why this plan" view.
4. **Wire the audit dashboard to the validator** — run
   `validation/loader.load_content()` on demand (or read the latest
   `docs/audits/*.json`) to show live schema/referential-integrity error counts
   alongside the freshness data.
5. **Diff view in the verification queue** — render the YAML diff for a
   `KbReview` (from `branch_name`/`pr_number`) so reviewers approve content, not
   just a summary line.
```
