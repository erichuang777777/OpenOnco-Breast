# Migration draft — Prostate adenocarcinoma (DIS-PROSTATE)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hereditary_prostate_cancer_risk.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Confirmed BRCA2 germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_brca2_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_brca2_pathogenic_variant_confirmed`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Confirmed BRCA1 germline pathogenic / likely-pathogenic variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_brca1_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_brca1_pathogenic_variant_confirmed`
- **`any_of[2]`** (step 1, SOLE_ANY): `condition: "Confirmed HOXB13 G84E (or other HOXB13 P/LP) germline variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[3]`** (step 1, SOLE_ANY): `condition: "Confirmed MLH1 / MSH2 / MSH6 / PMS2 / EPCAM germline pathogenic / likely-pathogenic variant (Lynch syndrome)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[4]`** (step 1, SOLE_ANY): `condition: "Confirmed ATM / PALB2 / CHEK2 (modest-risk) germline variant in male carrier with family-history of high-grade prostate cancer"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Male carrier with confirmed BRCA2 P/LP variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "Carrier age ≥40"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Male carrier with confirmed BRCA2 P/LP variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Carrier age <40"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Male carrier with confirmed BRCA1 P/LP variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "Carrier age ≥40"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Male carrier with confirmed HOXB13 G84E (or other HOXB13 P/LP) variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "Carrier age ≥40"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Male carrier with confirmed MLH1 / MSH2 / MSH6 / PMS2 / EPCAM germline P/LP variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 6, SOLE_ALL): `condition: "Carrier age ≥40"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_prostate_mcrpc_1l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "No prior ARPI (enzalutamide/abiraterone/apalutamide/darolutamide) in mHSPC"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "PSMA-PET/CT positive (all lesions PSMA-avid, no PSMA-negative sites with metastases)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Prior taxane AND prior ARPI both received (Lu-PSMA eligibility per VISION)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "ECOG PS 0-2 (docetaxel eligible)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "No prior taxane in mHSPC or mCRPC"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_prostate_mcrpc_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "ECOG PS 0-2"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "BRCA1 or BRCA2 somatic or germline pathogenic variant (or ATM, CDK12, PALB2, RAD51C/D, BRIP1, FANCA)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `brca1_status; brca2_somatic`
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "No prior PARPi therapy (olaparib, rucaparib, niraparib)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "PSMA-PET/CT positive (68Ga-PSMA-11 or 18F-DCFPyL) — ALL metastatic lesions PSMA-avid; no PSMA-negative metastatic sites"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Prior ARPI (enzalutamide, abiraterone, darolutamide, or apalutamide)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 3, SOLE_ALL): `condition: "Prior taxane-based chemotherapy (docetaxel) OR documented taxane-ineligible"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Prior docetaxel-based chemotherapy (mHSPC or mCRPC setting)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "Visceral metastases present (liver, lung, brain, or peritoneal mets)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `brain_metastases`
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Symptomatic bone metastases (bone pain or prior SSE)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 6, SOLE_ALL): `condition: "ECOG PS 0-2"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[2]`** (step 6, SOLE_ALL): `condition: "No concurrent novel ARPI planned (ERA 223 fracture harm)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 6, SOLE_ALL): `condition: "Nuclear medicine theranostics center accessible"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
