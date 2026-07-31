# Migration draft — Head and neck squamous cell carcinoma (HNSCC) (DIS-HNSCC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hnscc_rm_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "PD-L1 CPS ≥20 AND no rapid progression / visceral crisis AND ECOG 0-2"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `rapid_visceral_progression; ecog_status`
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "PD-L1 CPS ≥1"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_hnscc_rm_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "ECOG PS 0-2"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "No prior anti-PD-(L)1 therapy (ICI-naive) — received EXTREME or platinum-only 1L without pembrolizumab"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "PD-L1 CPS ≥20 AND pembrolizumab available"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
