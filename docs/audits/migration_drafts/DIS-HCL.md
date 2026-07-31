# Migration draft — Hairy Cell Leukemia (DIS-HCL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hcl_1l.yaml`

- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Treatment indication present (cytopenia or symptomatic splenomegaly)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "No active uncontrolled infection"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "active_uncontrolled_infection"}`
  - Candidate finding key(s): `active_uncontrolled_infection`

## `algo_hcl_2l.yaml`

- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "HCL relapse documented (cytopenia, splenomegaly, marrow infiltration) OR primary refractory after 1L purine"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `primary_refractory`
