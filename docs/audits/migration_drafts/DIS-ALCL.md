# Migration draft — Anaplastic Large Cell Lymphoma (systemic) (DIS-ALCL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_alcl_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "Brentuximab accessible (funding pathway)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_alcl_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Status post autoSCT in CR/PR"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "High-risk features present (primary refractory pre-ASCT, relapse <12 months from 1L, ≥2 prior lines, or extranodal at relapse)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Brentuximab vedotin not used in prior line"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "No baseline Grade ≥2 peripheral neuropathy"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "peripheral_neuropathy_grade"}`
  - Candidate finding key(s): `peripheral_neuropathy_grade`
- **`all_of[1]`** (step 3, MIXED_ALL): `condition: "Brentuximab vedotin previously administered"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
