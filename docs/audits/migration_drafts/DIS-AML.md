# Migration draft — Acute Myeloid Leukemia (non-APL) (DIS-AML)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_aml_1l.yaml`

- **`any_of[0]`** (step 7, SOLE_ANY): `condition: "Fit for intensive chemotherapy (default if no fitness flags)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_aml_2l.yaml`

- **`any_of[0]`** (step 8, SOLE_ANY): `condition: "FLT3 wild-type R/R AML; clinical-trial / re-induction / BSC routing surfaced as annotation"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
