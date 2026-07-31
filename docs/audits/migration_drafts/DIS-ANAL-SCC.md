# Migration draft — Squamous cell carcinoma of the anal canal (DIS-ANAL-SCC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_anal_scc_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Histology confirmed: squamous cell carcinoma of the anal canal"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "CT CAP and/or PET-CT completed for staging"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Locally advanced disease (any T, any N, M0) — stages I, II, or III"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "ECOG PS 0-2"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "No prior pelvic RT to dose-limiting cumulative dose"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 3, SOLE_ALL): `condition: "CrCl ≥50 mL/min and adequate hepatic function"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "ECOG PS 0-1"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "No active autoimmune disease requiring systemic immunosuppression"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "active_autoimmune_disease"}`
  - Candidate finding key(s): `active_autoimmune_disease`
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "Adequate organ function (CrCl ≥50 mL/min, normal LFTs)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
