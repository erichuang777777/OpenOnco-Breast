# Migration draft — Primary Mediastinal (Thymic) Large B-Cell Lymphoma (DIS-PMBCL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_pmbcl_2l.yaml`

- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "R-ICE x 2 cycles completed"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "Interim Deauville ≥4 (no metabolic response) — chemorefractory"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[3]`** (step 3, MIXED_ALL): `condition: "Age ≤65-70, (transplant-eligible)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[4]`** (step 3, MIXED_ALL): `condition: "First relapse OR primary refractory with chemosensitive disease"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `primary_refractory`
- **`all_of[5]`** (step 3, MIXED_ALL): `condition: "CD20+ confirmed at relapse biopsy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
