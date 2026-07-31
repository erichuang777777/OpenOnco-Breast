# Migration draft — Ovarian carcinoma (high-grade serous predominant) (DIS-OVARIAN)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_ovarian_2l.yaml`

- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Platinum-sensitive, HRD-negative or unknown — default re-induction chemo+bev"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_ovarian_advanced_1l.yaml`

- **`any_of[0]`** (step 6, SOLE_ANY): `condition: "HRD-negative or unknown"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `hrd_status`
