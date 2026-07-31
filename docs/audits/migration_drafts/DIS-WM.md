# Migration draft — Waldenström Macroglobulinemia / Lymphoplasmacytic Lymphoma (DIS-WM)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_wm_1l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "iwWM treatment indication present"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_wm_2l.yaml`

- **`all_of[2]`** (step 2, MIXED_ALL): `condition: "No high atrial fibrillation / cardiac risk precluding BTKi"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
