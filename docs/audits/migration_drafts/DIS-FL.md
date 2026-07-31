# Migration draft — Follicular Lymphoma (DIS-FL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_fl_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Rituximab-refractory (progression on or within 6 months of last rituximab)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "≥2 prior systemic lines"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "prior_lines"}`
  - Candidate finding key(s): `prior_lines`
- **`all_of[4]`** (step 2, MIXED_ALL): `condition: "CD19+ disease confirmed"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "disease"}`
  - Candidate finding key(s): `disease`
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Transplant-ineligible OR CAR-T inaccessible"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `transplant_eligible`
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "EZH2-WT and patient prefers chemo-free off-the-shelf"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `ezh2_status`
