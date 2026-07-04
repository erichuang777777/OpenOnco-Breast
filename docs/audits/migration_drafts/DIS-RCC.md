# Migration draft — Renal cell carcinoma (DIS-RCC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_rcc_metastatic_1l.yaml`

- **`all_of[0]`** (step 3a, SOLE_ALL): `condition: "IMDC favorable risk (0 adverse factors)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "imdc_risk"}`
  - Candidate finding key(s): `imdc_risk`
- **`all_of[1]`** (step 3a, SOLE_ALL): `condition: "ECOG PS 0-1 AND fit for ICI+TKI combination"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `ecog_status`
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "ECOG PS 0-1"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "High tumour burden OR conversion-to-resection intent OR rapid response needed"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "Significant bone metastases (MET/AXL pathway biological rationale for cabozantinib)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 5, SOLE_ANY): `condition: "Uncontrolled hypertension (lenvatinib toxicity concern)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "uncontrolled_hypertension"}`
  - Candidate finding key(s): `uncontrolled_hypertension`
- **`any_of[2]`** (step 5, SOLE_ANY): `condition: "ECOG PS 1-2 (better tolerability of nivo+cabo vs lenv+pembro)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_rcc_metastatic_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Prior PD-(L)1 + VEGF-TKI failure"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_vhl_carrier_surveillance_vhl_alliance.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Confirmed VHL germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_vhl_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_vhl_pathogenic_variant_confirmed`
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Carrier is age ≥1 — ophthalmologic surveillance entry"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Dilated fundus exam (ophthalmologist with retinal expertise) q6-12 months in childhood; q1y from adolescence — retinal hemangioblastoma surveillance"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Audiology q1-2y from age 5 — endolymphatic sac tumor surveillance (hearing loss is sentinel feature)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 3, SOLE_ALL): `condition: "Brain + spinal cord MRI with contrast (gadolinium) q2y from age 11-15 — cerebellar / brainstem / spinal cord hemangioblastoma surveillance; from age 30 q1y or based on growth"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Plasma OR urinary fractionated metanephrines q1y from age 5 — pheochromocytoma surveillance (bilateral / multifocal pattern typical of VHL); plasma free metanephrines preferred"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "Abdominal MRI with contrast q2y from age 15 — RCC + pancreatic NET / cyst + adrenal pheochromocytoma surveillance; from age 30 alternate q1y MRI / q1y US or maintain q2y MRI"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "BP measurement q1y (symptomatic pheochromocytoma may present with hypertension)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "RCC surgical threshold: tumor diameter ≥3 cm typically triggers partial nephrectomy / nephron-sparing surgery (delayed surgery for tumors <3 cm preserves renal function across lifetime per VHL Alliance — active surveillance with q6-12 month imaging is acceptable for sub-3-cm tumors)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "Pheochromocytoma surgical threshold: any functional pheochromocytoma + asymptomatic adrenal lesion >3 cm OR with biochemical elevation"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 5, SOLE_ALL): `condition: "Cascade testing offered to all first-degree relatives at any age (pediatric appropriate — surveillance entry from age 1)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
