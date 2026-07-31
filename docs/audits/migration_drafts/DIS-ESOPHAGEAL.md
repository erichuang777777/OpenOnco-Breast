# Migration draft — Esophageal carcinoma (squamous + adeno) (DIS-ESOPHAGEAL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_esoph_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, MIXED_ALL): `condition: "PD-L1 CPS ≥10 (22C3 assay)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "No prior ICI in 1L"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 1, MIXED_ALL): `condition: "No active autoimmune disease"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "active_autoimmune_disease"}`
  - Candidate finding key(s): `active_autoimmune_disease`
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "Squamous-cell histology"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "No prior ICI in 1L"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 2, MIXED_ALL): `condition: "No active autoimmune disease"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "active_autoimmune_disease"}`
  - Candidate finding key(s): `active_autoimmune_disease`

## `algo_esoph_definitive_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[1].any_of[0]`** (step 1, SOLE_ANY): `condition: "cT4b — unresectable due to invasion of adjacent structures"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1].any_of[1]`** (step 1, SOLE_ANY): `condition: "M0 medically inoperable (cardiopulmonary or comorbidity contraindications)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[2]`** (step 1, SOLE_ANY): `condition: "Patient declines surgery"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_esoph_metastatic_1l.yaml`

- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "PD-L1 CPS ≥ 1 (22C3 or 28-8 assay)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[0]`** (step 4, SOLE_ANY): `condition: "PD-L1 CPS >= 10"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[1]`** (step 4, SOLE_ANY): `condition: "PD-L1 CPS ≥ 10"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_esoph_resectable_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, MIXED_ALL): `condition: "cT1b-T4a or N+ M0 (resectable / borderline)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
