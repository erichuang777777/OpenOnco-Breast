# Migration draft — Cutaneous melanoma (DIS-MELANOMA)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hereditary_melanoma_surveillance.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Confirmed CDKN2A germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_cdkn2a_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_cdkn2a_pathogenic_variant_confirmed`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Confirmed CDK4 germline pathogenic / likely-pathogenic variant (codon 24 R24H / R24C — gain-of-function)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 1, SOLE_ANY): `condition: "Confirmed MITF E318K germline variant (modest melanoma + RCC risk)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[3]`** (step 1, SOLE_ANY): `condition: "Confirmed POT1 germline pathogenic variant (familial melanoma + glioma)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Confirmed CDKN2A or CDK4 or MITF or POT1 carrier identified at step 1"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "≥3 confirmed melanoma cases (cutaneous or uveal) in a single family across any generations, including ≥1 with pancreatic adenocarcinoma"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "≥2 first-degree relatives with cutaneous melanoma"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[2]`** (step 3, SOLE_ANY): `condition: "Proband with ≥3 primary cutaneous melanomas"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[3]`** (step 3, SOLE_ANY): `condition: "Proband with cutaneous melanoma + pancreatic adenocarcinoma at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "≥50 atypical / dysplastic nevi on whole-body exam"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "Personal history of cutaneous melanoma OR ≥1 first-degree relative with melanoma"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_melanoma_metastatic_2l.yaml`

- **`any_of[0]`** (step 41, SOLE_ANY): `condition: "Patient fit for ipi+nivo Grade 3-4 irAE risk (ECOG 0-1, no significant baseline autoimmunity)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
