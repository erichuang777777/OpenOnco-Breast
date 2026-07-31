# Migration draft — Post-Transplant Lymphoproliferative Disorder (DIS-PTLD)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_ptld_1l.yaml`

- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "EBV-positive on tumor EBER-ISH OR detectable plasma EBV-DNA"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `ebv_status_tumor`
- **`all_of[2]`** (step 2, MIXED_ALL): `condition: "CD20-positive histology"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "cd20_status"}`
  - Candidate finding key(s): `cd20_status`
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "EBV-negative on tumor EBER-ISH AND undetectable plasma EBV-DNA"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `ebv_status_tumor`
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "CD20-positive histology"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "cd20_status"}`
  - Candidate finding key(s): `cd20_status`

## `algo_ptld_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, MIXED_ALL): `condition: "CR or PR after initial rituximab × 4 weekly induction"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
