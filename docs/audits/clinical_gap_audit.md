# Clinical gap audit

Generated: `2026-05-31T10:01:22Z`

This is a coverage/governance audit, not a clinical recommendation set.
It makes the five largest known gaps measurable and repeatable.

## Summary

| Gap | Current | Target | Status |
|---|---:|---|---|
| Clinical sign-off | 15/2341 signoff-eligible entities reviewed (0.6%) | >=85% reviewed before public guideline-grade claims | `blocked_on_reviewers` |
| Solid tumor 2L+ coverage | 23/56 solid diseases have a 2L+ algorithm; 24/56 have a 2L+ indication | Every modeled solid disease has at least one advanced/relapsed-line algorithm and indication. | `coverage_gap` |
| Surgery/radiation detail | structured surgery entities: no; structured radiation entities: no; 649 indications mention surgery/radiation in text | Dedicated modality entities for surgery and radiation with dose/fraction/intent/timing fields. | `schema_gap` |
| Supportive-care depth | 135/384 regimens have mandatory supportive care (35.2%); 43 have monitoring; 341 have dose adjustments | Every active regimen has supportive care, monitoring, dose-adjustment, and patient-watchpoint coverage. | `coverage_gap` |
| Drug indication and off-label tracking | 821 drug-disease-indication pairs inferred from regimens; 0 carry explicit labeled/off-label status | Every drug-use pair has explicit regulatory-label status, NCCN/ESMO category, and source provenance. | `schema_gap` |

## Next actions

### Clinical sign-off

- Blocker: Cannot be fixed by code; requires qualified Clinical Co-Lead review.
- Next action: Batch the largest STUB queues by entity type and assign reviewer owners.

### Solid tumor 2L+ coverage

- Blocker: Missing disease-by-disease 2L+ algorithm/indication authoring queue.
- Next action: Prioritize missing high-volume solid diseases, then rare solid diseases.
- Missing 2L+ algorithm rows: 33
  - `DIS-ADRENOCORTICAL-CARCINOMA`: Adrenocortical carcinoma
  - `DIS-ANAL-SCC`: Anal squamous cell carcinoma (Anal SCC)
  - `DIS-BCC`: Basal cell carcinoma
  - `DIS-CERVICAL`: Cervical carcinoma
  - `DIS-CHONDROSARCOMA`: Chondrosarcoma
  - `DIS-CHOROID-PLEXUS-CARCINOMA`: Choroid plexus carcinoma
  - `DIS-EPITHELIOID-SARCOMA`: Epithelioid sarcoma
  - `DIS-GI-NET`: GI neuroendocrine tumor (carcinoid)
  - `DIS-GLIOMA-LOW-GRADE`: Low-grade glioma
  - `DIS-GRANULOSA-CELL`: Adult granulosa cell tumor
  - `DIS-IFS`: Infantile fibrosarcoma
  - `DIS-IMT`: Inflammatory myofibroblastic tumor
  - `DIS-KAPOSI`: Kaposi sarcoma
  - `DIS-LAM`: Lymphangioleiomyomatosis
  - `DIS-LARYNGEAL`: Laryngeal squamous cell carcinoma
  - `DIS-LEIOMYOSARCOMA`: Leiomyosarcoma
  - `DIS-MENINGIOMA`: Meningioma
  - `DIS-MPNST`: Malignant peripheral nerve sheath tumor
  - `DIS-MTC`: Medullary thyroid carcinoma
  - `DIS-NPC`: Nasopharyngeal carcinoma
  - `DIS-OSTEOSARCOMA`: Osteosarcoma
  - `DIS-PARATHYROID-CARCINOMA`: Parathyroid carcinoma
  - `DIS-PENILE-SCC`: Penile squamous cell carcinoma
  - `DIS-PHEOCHROMOCYTOMA`: Pheochromocytoma
  - `DIS-PITUITARY-ADENOMA`: Pituitary adenoma

### Surgery/radiation detail

- Blocker: Current KB carries surgery/radiation mostly as prose inside indications.
- Next action: Add modality schemas first; migrate prose mentions after clinical review.

### Supportive-care depth

- Blocker: Supportive-care records exist, but regimen attachment is incomplete.
- Next action: Audit high-toxicity regimens first, then fill missing regimen attachments.
- Regimens missing mandatory supportive care: 120 shown below
  - `REG-2GEN-TKI-CML`
  - `REG-5FU-LV-BEV-CKD-MODIFIED`
  - `REG-ABEMACICLIB-ADJUVANT`
  - `REG-ACALABRUTINIB-CONTINUOUS`
  - `REG-ACALABRUTINIB-MCL`
  - `REG-ACALABRUTINIB-RITUXIMAB`
  - `REG-ADAGRASIB-NSCLC`
  - `REG-ALECTINIB-NSCLC`
  - `REG-ALLOHCT-JMML`
  - `REG-ALPELISIB-FULVESTRANT-BREAST`
  - `REG-AMI-LAZ-NSCLC`
  - `REG-AMIVANTAMAB-LAZERTINIB-NSCLC-2L`
  - `REG-AMIVANTAMAB-MONO-NSCLC-EX20INS`
  - `REG-ANAGRELIDE-ET`
  - `REG-ASCIMINIB-CML`
  - `REG-ATEZO-ADJUVANT-NSCLC`
  - `REG-ATEZO-BEV`
  - `REG-AVAPRITINIB-ADVSM-1L`
  - `REG-AVAPRITINIB-GIST-1L`
  - `REG-AVELUMAB-MAINTENANCE`
  - `REG-AVELUMAB-MONO-NK-T`
  - `REG-BELZUTIFAN-MONO`
  - `REG-BEMARITUZUMAB-MFOLFOX6`
  - `REG-BEP-GCT`
  - `REG-BEV-MAINTENANCE-OVARIAN`
  - `REG-BEVACIZUMAB-GBM`
  - `REG-BEXAROTENE-MAINTENANCE-CTCL`
  - `REG-BEXAROTENE-MONO-CTCL`
  - `REG-BV-MONO-MF`
  - `REG-CABAZITAXEL-MCRPC`
  - `REG-CABOZANTINIB-HCC`
  - `REG-CABOZANTINIB-MTC-1L`
  - `REG-CABOZANTINIB-RCC`
  - `REG-CAPE-BEV-MAINTENANCE`
  - `REG-CAPECITABINE-CRT-CONCURRENT`
  - `REG-CAPECITABINE-PALLIATIVE`
  - `REG-CAPIVASERTIB-FULVESTRANT-BREAST`
  - `REG-CAPMATINIB-NSCLC`
  - `REG-CAPOX`
  - `REG-CAR-T-AXICEL-HGBL`

### Drug indication and off-label tracking

- Blocker: No first-class drug_indications entity directory/schema is present.
- Next action: Introduce a drug_indications entity, then backfill from existing indications/regimens.
- Inferred pairs to backfill: 821
- Explicit labeled/off-label statuses: 0

## Machine-readable outputs

- `docs/audits/clinical_gap_audit.json`
- `docs/audits/clinical_gap_audit.md`
- `docs/clinical-gaps.html`
