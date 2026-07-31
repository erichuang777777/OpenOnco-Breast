# Migration draft — HCV-associated Marginal Zone Lymphoma (DIS-HCV-MZL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hcv_mzl_1l.yaml`

- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "HCV RNA positive"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "hcv_rna"}`
  - Candidate finding key(s): `hcv_rna`
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "Indolent presentation (non-bulky, asymptomatic or minimally symptomatic)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_hcv_mzl_2l.yaml`

- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Documented lymphoma progression on imaging or biopsy after DAA"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "No documented relapse / progression"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
