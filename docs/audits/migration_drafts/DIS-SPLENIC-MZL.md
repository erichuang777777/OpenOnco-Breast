# Migration draft — Splenic Marginal Zone Lymphoma (DIS-SPLENIC-MZL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_smzl_1l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "HCV RNA negative OR no antiviral candidate"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `hcv_rna`
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "CD20+ histology confirmed"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "cd20_status"}`
  - Candidate finding key(s): `cd20_status`
