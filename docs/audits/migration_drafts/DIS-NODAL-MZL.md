# Migration draft — Nodal Marginal Zone Lymphoma (DIS-NODAL-MZL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_nmzl_1l.yaml`

- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "HCV RNA positive (anti-HCV alone insufficient)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "hcv_rna"}`
  - Candidate finding key(s): `hcv_rna`
- **`all_of[2]`** (step 2, MIXED_ALL): `condition: "Compensated liver function (no decompensated cirrhosis)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "decompensated_cirrhosis"}`
  - Candidate finding key(s): `decompensated_cirrhosis`
- **`all_of[3]`** (step 2, MIXED_ALL): `condition: "Indolent / low-burden presentation (GELF-negative)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
