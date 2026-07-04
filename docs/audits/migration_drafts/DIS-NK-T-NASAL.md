# Migration draft — Extranodal NK/T-Cell Lymphoma, Nasal Type (DIS-NK-T-NASAL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_nk_t_nasal_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, MIXED_ALL): `condition: "Age ≤ 70"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "age"}`
  - Candidate finding key(s): `age`
- **`all_of[3]`** (step 1, MIXED_ALL): `condition: "L-asparaginase access available"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
