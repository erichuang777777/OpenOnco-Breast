# Migration draft — Primary Diffuse Large B-Cell Lymphoma of the CNS (DIS-PCNSL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_pcnsl_2l.yaml`

- **`all_of[0]`** (step 3, MIXED_ALL): `condition: "Documented CR or PR to 1L HD-MTX-based regimen"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, MIXED_ALL): `condition: "Late relapse: ≥6 months from 1L completion"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
