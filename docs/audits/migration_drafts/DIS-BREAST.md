# Migration draft — Breast cancer (invasive) (DIS-BREAST)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_bcsc_breast.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Patient has known BRCA1/BRCA2 pathogenic variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "brca1_brca2_pathogenic"}`
  - Candidate finding key(s): `brca1_brca2_pathogenic`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Patient has strong family history suggesting HBOC (use pedigree-based model)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 1, SOLE_ANY): `condition: "Patient had prior chest/thoracic radiation"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[3]`** (step 1, SOLE_ANY): `condition: "Patient has personal history of breast cancer or DCIS / LCIS"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[4]`** (step 1, SOLE_ANY): `condition: "Patient age <35 or >74 (outside BCSC validation range)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "BCSC 10-year invasive breast cancer risk ≥6% (high-risk threshold approximating lifetime ≥20-30%)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "BCSC 5-year invasive breast cancer risk ≥3.0%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "BI-RADS density category c (heterogeneously dense) or d (extremely dense)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "BCSC 5-year invasive breast cancer risk ≥1.66%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_boadicea_v6_breast_ovarian.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "BOADICEA v6 lifetime breast cancer risk ≥30% (NICE high-risk threshold)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "BOADICEA v6 lifetime breast cancer risk ≥20% (ACS/NCCN MRI-eligibility threshold)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "BOADICEA v6 carrier probability ≥10% for any of BRCA1, BRCA2, PALB2, CHEK2, ATM, RAD51C, RAD51D, BARD1 (combined or per-gene)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "BOADICEA v6 lifetime ovarian / fallopian / primary peritoneal cancer risk ≥3%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "BOADICEA v6 lifetime pancreatic cancer risk ≥5%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_brcapro.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "BRCAPRO combined BRCA1 + BRCA2 carrier probability ≥20%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "BRCAPRO combined BRCA1 + BRCA2 carrier probability ≥10%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "BRCAPRO combined BRCA1 + BRCA2 carrier probability ≥2.5%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_breast_1l.yaml`

- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Stage I-III (early HR+/HER2-)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "stage_iii"}`
  - Candidate finding key(s): `stage_iii`
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "High-risk: ≥4 axillary nodes OR (1-3 nodes + Ki67 ≥20% or grade 3) — monarchE eligibility"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_breast_her2_pos_2l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Brain metastases present (active OR previously treated, stable or progressing)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `brain_metastases`
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "MRI brain confirms intracranial disease ≤2 cm OR symptomatic ≥2 cm post-local therapy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "No brain metastases OR brain mets not the dominant clinical issue"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `brain_metastases`

## `algo_breast_hr_pos_2l.yaml`

- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "≥1 prior chemo line for metastatic disease OR rapid progression on endocrine"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{any_of: [{finding: "metastatic_disease"}, {finding: "rapid_progression"}]}`
  - Candidate finding key(s): `metastatic_disease; rapid_progression`
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "No PIK3CA / AKT1 / PTEN / ESR1 alteration AND HER2 IHC 0"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `her2_ihc`

## `algo_breast_tnbc_2l.yaml`

- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "≥1 prior chemo line for metastatic disease"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "metastatic_disease"}`
  - Candidate finding key(s): `metastatic_disease`
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Non-BRCA AND HER2 IHC 0 metastatic TNBC ≥2L"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `her2_ihc`

## `algo_cowden_carrier_surveillance.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Confirmed PTEN germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_pten_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_pten_pathogenic_variant_confirmed`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Clinical PHTS / Cowden syndrome (NCCN Cowden / PHTS major + minor criteria met) without confirmed PTEN variant — empirical-surveillance pathway"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Carrier is age ≥7 (thyroid surveillance entry) — pediatric thyroid US recommended from age 7-10 per NCCN PHTS"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Carrier is female age ≥30 OR carrier of any sex with personal history of Cowden-spectrum cancer"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Annual breast MRI from age 30 + annual mammography from age 30-35 (alternating q6 mo cadence acceptable per NCCN); clinical breast exam q6 mo from age 25; breast self-awareness counseling"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Thyroid US q1y from age 7 (pediatric entry) or from identification if adult — entry irrespective of carrier sex"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "Endometrial sampling (transvaginal US ± endometrial biopsy) q1y from age 30-35 in female carriers; alternately patient education on early-symptom reporting (abnormal uterine bleeding) — sampling q1y is conservative cadence; some centers defer to symptom-driven evaluation per NCCN PHTS"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "Colonoscopy q5y from age 35 (NCCN PHTS — earlier cadence q1-3y if hamartomatous polyposis identified)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 4, SOLE_ALL): `condition: "Renal imaging (US or MRI) q2y from age 40"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[4]`** (step 4, SOLE_ALL): `condition: "Annual whole-body dermatologic exam (mucocutaneous features + melanoma surveillance)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_gail_breast.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Patient has known BRCA1/BRCA2 pathogenic variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "brca1_brca2_pathogenic"}`
  - Candidate finding key(s): `brca1_brca2_pathogenic`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Patient has strong family history suggesting HBOC (use Manchester / Tyrer-Cuzick / BOADICEA instead)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 1, SOLE_ANY): `condition: "Patient had prior chest/thoracic radiation (e.g., Hodgkin lymphoma treatment)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[3]`** (step 1, SOLE_ANY): `condition: "Patient has personal history of breast cancer or LCIS / DCIS"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Gail 5-year invasive breast cancer risk ≥1.66%"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Gail 5-year invasive breast cancer risk ≥3.0%"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Gail lifetime risk ≥20%"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_manchester_brca.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Manchester combined BRCA1 + BRCA2 score ≥15 points"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Triple-negative breast cancer at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "Breast cancer diagnosed at age <46 regardless of family history"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[2]`** (step 2, SOLE_ANY): `condition: "Male breast cancer at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[3]`** (step 2, SOLE_ANY): `condition: "Ovarian cancer (epithelial non-mucinous) at any age regardless of family history"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "family_ovarian_cancer_any_age"}`
  - Candidate finding key(s): `family_ovarian_cancer_any_age`
- **`any_of[4]`** (step 2, SOLE_ANY): `condition: "Ashkenazi Jewish ancestry with breast or ovarian cancer at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_tyrer_cuzick_v8_breast.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Tyrer-Cuzick v8 lifetime breast cancer risk ≥30% (NICE high-risk threshold)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Tyrer-Cuzick v8 lifetime breast cancer risk ≥20% (ACS/NCCN MRI-eligibility threshold)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Tyrer-Cuzick v8 10-year breast cancer risk ≥3% (NCCN BRSK chemoprevention-discussion threshold)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Tyrer-Cuzick v8 BRCA1/2 carrier probability ≥10%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
