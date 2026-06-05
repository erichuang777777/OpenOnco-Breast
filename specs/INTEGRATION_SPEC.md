# Integration Specification — External Hospital Systems

**Version:** 0.1 draft  
**Status:** pending clinical-lead review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Overview

OpenOnco Hospital Edition exposes two external integration targets:

| Target | Direction | Protocol | Standard |
|--------|-----------|----------|----------|
| 個案管理系統 (CMS) | Bidirectional | REST + FHIR R4 | HL7 FHIR R4 + mCODE STU3 |
| 藥物申請系統 (DAS) | Outbound only | REST JSON | Hospital-specific + NHI schema |

CHARTER §8.3 invariant is maintained throughout: clinical decisions come from
the rule engine reading versioned KB YAML.  Neither integration target sends
data to an LLM nor receives LLM-generated clinical recommendations.

---

## 2  個案管理系統 (Case Management System)

### 2.1  Inbound — patient import

```
CMS ──FHIR Bundle──► fhir_bundle_to_patient() ──► generate_plan() ──► PlanResult
```

The CMS sends a FHIR R4 searchset Bundle containing:

| Resource | Purpose | Key fields |
|----------|---------|------------|
| `Patient` | Demographics + MRN | `birthDate`, `gender`, `identifier[MR]` |
| `Condition` | Primary diagnosis + stage | `code.coding[ICD-10]`, `stage.summary.coding[SNOMED]` |
| `Observation` | Biomarkers / labs | `code.coding[LOINC]` + value (see §2.4) |
| `EpisodeOfCare` | Line of therapy | `type.coding[line-N]` |

Adapter module: `knowledge_base/integrations/case_management.py`  
Function: `fhir_bundle_to_patient(bundle: dict) → patient_dict`

Unknown LOINC codes and unmapped ICD-10 prefixes are silently skipped.
The engine handles missing fields via its safe-default rule (unknown
findings default to `False`).

### 2.2  Outbound — plan push

```
PlanResult ──► plan_result_to_fhir_care_plan() ──► FHIR CarePlan ──► CMS
```

Output resource: `CarePlan` (R4) with:
- `status: draft` until clinician activates via CMS
- One `activity` per PlanTrack (default track first)
- `note[]` for MDT open questions and engine warnings
- Extension `openonco:plan-id` for audit linkage

CMS must display CarePlan with status `draft` and require clinician
activation before the plan appears in the patient record as `active`.

Function: `plan_result_to_fhir_care_plan(result, patient_fhir_id) → dict`

### 2.3  Outbound — decision gaps as ServiceRequests

When the engine's two-pass diff surfaces missing fields that would change
the treatment recommendation, the adapter generates FHIR `ServiceRequest`
resources (status `draft`) representing the recommended tests.

Function: `decision_gaps_to_fhir_service_requests(gaps, patient_fhir_id)`

### 2.4  LOINC → findings mapping (breast cancer)

| LOINC | Finding key | Description |
|-------|-------------|-------------|
| 85319-2 | `her2_ihc` | HER2 IHC score |
| 85325-9 | `her2_ish` | HER2 ISH (amplified / non-amplified) |
| 18474-7 | `her2_status` | HER2 status summary |
| 85337-4 | `er_status` | ER IHC (positive / negative) |
| 85339-0 | `pr_status` | PR IHC (positive / negative) |
| 55233-1 | `brca1` | BRCA1 germline status |
| 55107-7 | `brca2` | BRCA2 germline status |
| 85147-7 | `pdl1_cps` | PD-L1 CPS score |
| 21908-9 | `stage_group` | Clinical stage group |
| 21902-2 | `stage_group` | Pathologic stage group |
| 89243-0 | `ecog` | ECOG PS |
| 94077-4 | `esr1_mutation` | ESR1 mutation (ctDNA) |
| 94076-6 | `pik3ca_mutation` | PIK3CA mutation |

Extend `knowledge_base/integrations/fhir_adapter.py::LOINC_TO_FINDING`
for additional disease sites.

### 2.5  ICD-10 prefix → disease id mapping

| ICD-10 prefix | Disease id |
|---------------|------------|
| C50 | DIS-BREAST |
| C34 | DIS-LUNG |
| C16 | DIS-GASTRIC |
| C18–C20 | DIS-COLORECTAL |
| C91 | DIS-LEUKEMIA-ALL |
| C92 | DIS-LEUKEMIA-AML |

Extend `fhir_adapter.py::ICD10_TO_DISEASE` for additional sites.

---

## 3  藥物申請系統 (Drug Application System)

### 3.1  Flow

```
PlanResult + track_id + patient metadata
        │
        ▼
  build_drug_requisition()
        │
        ▼
  DrugRequisition (dataclass)
        │
   ┌────┴────┐
   ▼         ▼
JSON POST  PDF render
  to DAS    (portal)
```

The clinician selects a track in the clinic or tumor-board portal, fills
in patient demographic fields (MRN, name initials, birth year), and
confirms the prescribing physician.  The portal calls
`build_drug_requisition()` and POSTs the resulting JSON to the DAS API
endpoint, or opens a print preview.

Module: `knowledge_base/integrations/drug_application.py`  
Function: `build_drug_requisition(plan_result, track_id, *, patient_mrn, ...) → DrugRequisition`

### 3.2  DrugRequisition schema

| Section | Fields |
|---------|--------|
| Identifiers | `requisition_id`, `created_date` |
| Patient | `patient_mrn`, `patient_name_initials`, `patient_birth_year`, `patient_sex` |
| Clinical context | `diagnosis_icd10`, `diagnosis_text`, `stage`, `treatment_intent`, `line_of_therapy`, `key_biomarkers` |
| Plan linkage | `indication_id`, `plan_id`, `plan_track_id` |
| Regimen | `regimen_id`, `regimen_name_en`, `regimen_name_zh`, `cycle_length_days`, `total_cycles`, `components[]` |
| Evidence | `evidence.nccn_category`, `evidence.nccn_category_zh`, `evidence.esmo_grade`, `evidence.pivotal_trial_nct[]`, `evidence.source_ids[]` |
| NHI/approval | `nhi_benefit_code`, `requires_prior_auth`, `special_approval_rationale` |
| Safety | `key_toxicities[]`, `monitoring_requirements[]` |

### 3.3  Dosing source guarantee (CHARTER §8.3)

Dose, route, and schedule fields are copied verbatim from the KB regimen
YAML `components[].dose`, `components[].route`, `components[].schedule`.
No LLM or calculation modifies these values.  The clinician is responsible
for confirming that dosing is appropriate for the individual patient.

### 3.4  Special approval rationale

`special_approval_rationale` is an auto-drafted template paragraph that
references the NCCN category, ESMO grade, and pivotal trial NCT numbers.
It ends with `【請主治醫師依個案情況補充說明並確認】` to require
clinician review before submission.  Do not submit without editing.

### 3.5  高價藥 (high-cost drug) flag

`requires_prior_auth` is set to `True` when the regimen name contains
keywords associated with high-cost drugs requiring NHI prior authorisation:
ADCs (T-DXd, Dato-DXd, sacituzumab), CDK4/6 inhibitors, PARP inhibitors,
PI3K/AKT inhibitors, pertuzumab + trastuzumab combinations.  The flag
triggers the hospital prior-auth workflow in the DAS.

---

## 4  API endpoints (hospital portal)

These endpoints wrap the integration adapters and are implemented in the
FastAPI layer (`api/hospital/`):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/plan/from-fhir` | Accept FHIR Bundle, return PlanResult JSON |
| `PUT`  | `/api/v1/cases/{mrn}/care-plan` | Push CarePlan to CMS via FHIR |
| `POST` | `/api/v1/cases/{mrn}/service-requests` | Push decision-gap ServiceRequests to CMS |
| `POST` | `/api/v1/drug-requisition` | Build and POST DrugRequisition to DAS |
| `GET`  | `/api/v1/drug-requisition/{id}/preview` | HTML preview of requisition |

Authentication: hospital OAuth 2.0 / SAML 2.0 SSO (out of scope for this spec;
handled by reverse proxy / API gateway layer).

---

## 5  Security and data handling

- **No PHI enters git** — all patient data is runtime-only (CHARTER §9.3).
- **CMS credentials** are stored as environment variables / secrets manager,
  never in source code or YAML KB.
- **FHIR base URL** is configured per deployment; no hardcoded URLs in code.
- **Audit log**: every `POST /plan/from-fhir` call records
  `(timestamp, patient_mrn_hash, disease_id, algorithm_id, plan_id)` to the
  hospital audit database (outside this repo).
- **CarePlan status = draft**: the engine never autonomously activates a
  CarePlan; that action requires a named clinician in the CMS.

---

## 6  Extending to other disease sites

To add gastric or lung cancer:

1. Extend `ICD10_TO_DISEASE` in `fhir_adapter.py` with the new ICD-10 prefix.
2. Add LOINC codes for site-specific biomarkers to `LOINC_TO_FINDING`.
3. Add ICD-10 code and Chinese name to `_disease_to_icd10()` and
   `_disease_to_zh()` in `drug_application.py`.
4. Ensure the corresponding `DIS-*` entity and algorithms exist in the KB.

No changes to the adapter interface are needed; the engine handles the new
disease automatically via its YAML routing.

---

## 7  Known limitations (v0.1)

- `name_zh` for drug components is currently populated from the `ukrainian`
  field in drug YAML (a historical artefact).  A dedicated `name_zh` /
  `brand_name_tw` field should be added to the drug schema in a future KB
  schema revision.
- NHI benefit codes (`nhi_benefit_code`) require a separate Taiwan NHI
  formulary lookup table — not yet integrated.
- CMS FHIR base URL and OAuth flow are out of scope for this spec;
  configure via deployment environment variables.
- Line-of-therapy extraction from `EpisodeOfCare` is heuristic; validate
  against CMS's actual coding scheme before deployment.
