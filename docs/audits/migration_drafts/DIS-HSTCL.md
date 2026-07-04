# Migration draft — Hepatosplenic T-Cell Lymphoma (DIS-HSTCL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hstcl_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "Age ≤ 65 OR fit"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `age`
- **`all_of[2]`** (step 1, MIXED_ALL): `condition: "AlloSCT donor pathway feasible (matched donor identified or imminent)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
