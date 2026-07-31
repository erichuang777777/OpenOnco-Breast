# Migration draft — Chronic Lymphocytic Leukemia / Small Lymphocytic Lymphoma (DIS-CLL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_cll_1l.yaml`

- **`all_of[1]`** (step 4, MIXED_ALL): `condition: "No major anti-CD20 or obinutuzumab contraindication (e.g., active HBV reactivation risk unmanaged, severe infusion history)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
