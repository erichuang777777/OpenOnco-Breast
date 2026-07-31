# Migration draft — High-Grade B-Cell Lymphoma with MYC and BCL2 and/or BCL6 rearrangements (double-hit / triple-hit) (DIS-HGBL-DH)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hgbl_dh_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "Continuous-infusion DA-EPOCH-R logistically feasible"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_hgbl_dh_2l.yaml`

- **`all_of[0]`** (step 3, MIXED_ALL): `condition: "Late relapse: ≥12 months from end of 1L therapy"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[4]`** (step 3, MIXED_ALL): `condition: "Transplant-eligible: age ≤65-70, adequate organ function"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[5]`** (step 3, MIXED_ALL): `condition: "Chemosensitive disease (≥PR to 2 cycles of salvage)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[6]`** (step 3, MIXED_ALL): `condition: "CD20+ confirmed at relapse biopsy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
