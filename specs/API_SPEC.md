# API Specification

**Version:** 0.1 draft  
**Status:** pending review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Conventions

- Base path: `/api/v1/`
- Content-Type: `application/json` (all endpoints)
- Auth header: `Authorization: Bearer <jwt>`
- Errors: `{"error": "<code>", "message": "<human-readable>"}` with appropriate HTTP status
- Timestamps: ISO-8601 UTC (`2026-06-03T07:23:00Z`)
- Patient MRN: always a string; never logged in plaintext (audit uses SHA-256 hash)

---

## 2  Plan generation

### `POST /api/v1/plan`

Generate a treatment or diagnostic plan from a structured patient dict.

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Request body:**
```json
{
  "patient": {
    "patient_id": "MRN-12345",
    "disease": {"id": "DIS-BREAST"},
    "line_of_therapy": 1,
    "demographics": {"age": 55, "sex": "female", "ecog": 1},
    "findings": {
      "her2_status": "positive",
      "er_status": "positive",
      "stage_group": "IV"
    },
    "biomarkers": {}
  },
  "include_mdt": true,
  "include_gaps": true
}
```

**Response `200`:**
```json
{
  "plan_id": "PLAN-20260603-A1B2",
  "disease_id": "DIS-BREAST",
  "algorithm_id": "ALGO-BREAST-1L",
  "tracks": [
    {
      "track_id": "T1",
      "label": "THP 1L (第一線 HER2+)",
      "is_default": true,
      "indication_id": "IND-BREAST-HER2-POS-MET-1L-THP",
      "regimen_id": "REG-THP-METASTATIC",
      "evidence_level": "high",
      "nccn_category": "1"
    }
  ],
  "mdt": { ... },
  "gaps": [
    {
      "field": "brain_mets",
      "tier": 2,
      "rationale": "Brain met status changes algorithm step 2",
      "would_change_to": "IND-BREAST-HER2-POS-3L-TUCATINIB"
    }
  ],
  "warnings": []
}
```

**Errors:** `422 MISSING_TIER1_FIELD` if required routing fields absent.

---

### `POST /api/v1/plan/gaps`

Run the two-pass decision-gap finder.  Same input as `/plan`.
Returns only the gap list without a full plan.

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Response `200`:**
```json
{
  "gaps": [
    {
      "field": "brca1",
      "tier": 2,
      "current_value": null,
      "if_positive_changes_to": "IND-BREAST-BRCA-POS-MET-PARPI",
      "rationale": "BRCA+ unlocks PARPi track (OlympiAD)",
      "recommended_test": "TEST-GERMLINE-BRCA-PANEL"
    }
  ]
}
```

---

### `GET /api/v1/plan/{plan_id}`

Retrieve a previously generated plan.

**Required roles:** all authenticated roles  
**Constraint:** `patient` role can only retrieve own plan IDs.

---

### `POST /api/v1/plan/{plan_id}/revise`

Generate a next-version plan superseding an existing one.

**Request body:**
```json
{
  "patient": { ... },
  "revision_trigger": "biopsy 2026-06-03 → BRCA1 positive"
}
```

---

## 3  Case management (internal)

### `POST /api/v1/cases`

Create a new case record.

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Request body:**
```json
{
  "mrn": "MRN-12345",
  "disease_id": "DIS-BREAST",
  "initial_plan_id": "PLAN-20260603-A1B2"
}
```

---

### `GET /api/v1/cases/{mrn}`

Get case summary with plan version chain.

**Response `200`:**
```json
{
  "mrn": "MRN-12345",
  "disease_id": "DIS-BREAST",
  "plans": [
    {
      "plan_id": "PLAN-20260603-A1B2",
      "version": 1,
      "created_at": "2026-06-03T07:23:00Z",
      "created_by": "dr-wang",
      "superseded_by": null,
      "selected_track_id": "T1"
    }
  ],
  "annotations": [ ... ]
}
```

---

### `POST /api/v1/cases/{mrn}/annotations`

Append a clinician annotation to a plan (append-only, no delete).

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Request body:**
```json
{
  "plan_id": "PLAN-20260603-A1B2",
  "annotation_type": "approve",
  "text": "MDT 2026-06-03 consensus: proceed with THP",
  "role": "medical_oncologist"
}
```

`annotation_type`: `approve` | `comment` | `flag` | `reject`

---

## 4  Drug requisition

### `POST /api/v1/drug-requisition`

Build a DrugRequisition from a selected track.

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Request body:**
```json
{
  "plan_id": "PLAN-20260603-A1B2",
  "track_id": "T1",
  "patient_mrn": "MRN-12345",
  "patient_name_initials": "陳O明",
  "patient_birth_year": "1970",
  "patient_sex": "女",
  "prescribing_physician": "王主治醫師"
}
```

**Response `200`:** Full `DrugRequisition` dict (see `drug_application.py`).

---

### `GET /api/v1/drug-requisition/{id}/preview`

Returns an HTML page suitable for print preview.  
Content-Type: `text/html`.

---

## 5  Clinical trial matching

### `GET /api/v1/trials`

Search ClinicalTrials.gov for trials matching patient profile.

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Query params:**
```
disease_id=DIS-BREAST
her2_status=positive
er_status=positive
stage=IV
country=Taiwan        # optional ISO country name
status=RECRUITING     # optional; default RECRUITING
```

**Response `200`:**
```json
{
  "trials": [
    {
      "nct_id": "NCT12345678",
      "title": "...",
      "phase": "III",
      "status": "RECRUITING",
      "eligibility_summary": "...",
      "locations": ["National Taiwan University Hospital", "..."],
      "url": "https://clinicaltrials.gov/study/NCT12345678"
    }
  ],
  "total": 12
}
```

Backed by `knowledge_base/clients/ctgov_client.py`.

---

## 6  LLM extraction

### `POST /api/v1/extract`

Convert free-text clinical note into a structured patient dict.

**Required roles:** `tumor_board_hcp`, `clinic_hcp`

**Request body:**
```json
{
  "text": "55歲女性，診斷HER2陽性轉移性乳癌，ER陽性，PR陰性，ECOG 1...",
  "language": "zh-TW",
  "conversation_id": null
}
```

`conversation_id`: null for new conversation; reuse returned ID for
follow-up turns (missing-field clarification).

**Response `200` — extraction complete:**
```json
{
  "conversation_id": "conv-abc123",
  "status": "complete",
  "patient": {
    "disease": {"id": "DIS-BREAST"},
    "demographics": {"age": 55, "sex": "female", "ecog": 1},
    "findings": {"her2_status": "positive", "er_status": "positive", "stage_group": "IV"},
    "biomarkers": {}
  },
  "gaps": ["brain_mets", "brca1"]
}
```

**Response `200` — clarification needed (Tier 1 missing):**
```json
{
  "conversation_id": "conv-abc123",
  "status": "needs_clarification",
  "question": "請問病患是否有腦部轉移的影像學紀錄？",
  "missing_field": "brain_mets",
  "tier": 2,
  "patient_partial": { ... }
}
```

Client should display `question` to HCP, collect answer, then re-POST with
`conversation_id` and `text` = the follow-up answer.  Maximum 2 rounds of
clarification; after that `status` = `complete` with remaining gaps listed.

See `specs/LLM_EXTRACTION_SPEC.md` for full extraction algorithm.

---

## 7  Render helpers

### `GET /api/v1/render/plan/{plan_id}`

Return rendered HTML for a plan.

**Query params:** `mode=clinician|patient|both`

For `mode=both`, returns `{"clinician_html": "...", "patient_html": "..."}`.  
For `mode=clinician` or `patient`, returns `{"html": "..."}`.

---

## 8  Admin — KB governance

### `GET /api/v1/admin/kb/reviews`

List KB entities awaiting clinical review (CHARTER §6.1 two-reviewer rule).

**Required roles:** `kb_admin`

**Response `200`:**
```json
{
  "pending": [
    {
      "review_id": "REV-001",
      "entity_type": "indication",
      "entity_id": "IND-BREAST-HER2-POS-MET-1L-THP",
      "submitted_by": "agent-session-xyz",
      "submitted_at": "2026-06-01T10:00:00Z",
      "reviewer_1": null,
      "reviewer_2": null,
      "diff_summary": "Added esr1_mutation field to required_tests"
    }
  ]
}
```

---

### `PATCH /api/v1/admin/kb/reviews/{review_id}`

Approve or reject a pending KB review.

**Required roles:** `kb_admin`

**Request body:**
```json
{"action": "approve", "comment": "Reviewed against NCCN 2025 §3.4"}
```

`action`: `approve` | `reject` | `request_changes`

Two distinct approvals required before entity is marked `approved`
(CHARTER §6.1).

---

## 9  Admin — audit

### `GET /api/v1/admin/audit`

Query the audit log.

**Required roles:** `auditor`, `kb_admin`

**Query params:** `mrn_hash`, `user_id`, `action`, `from`, `to`, `page`, `per_page`

---

## 10  Error codes

| HTTP | Code | Meaning |
|------|------|---------|
| 400 | `INVALID_PATIENT_DICT` | Patient JSON failed schema validation |
| 400 | `MISSING_TIER1_FIELD` | Routing-required field absent (use /extract first) |
| 401 | `UNAUTHENTICATED` | No / expired JWT |
| 403 | `INSUFFICIENT_ROLE` | Role claim does not permit this endpoint |
| 404 | `PLAN_NOT_FOUND` | plan_id unknown |
| 404 | `CASE_NOT_FOUND` | MRN unknown |
| 422 | `ENGINE_NO_ALGORITHM` | No matching algorithm for disease + line |
| 500 | `ENGINE_ERROR` | Unexpected engine exception (check logs) |
| 503 | `KB_NOT_LOADED` | KB YAML failed to load on startup |
