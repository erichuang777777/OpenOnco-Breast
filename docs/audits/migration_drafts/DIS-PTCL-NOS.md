# Migration draft — Peripheral T-Cell Lymphoma, Not Otherwise Specified (DIS-PTCL-NOS)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_ptcl_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "Romidepsin accessible (named-patient or trial)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 1, MIXED_ALL): `condition: "No baseline cardiac arrhythmia / QTc prolongation precluding HDACi"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "baseline_cardiac_arrhythmia"}`
  - Candidate finding key(s): `baseline_cardiac_arrhythmia`
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "Pralatrexate accessible (named-patient or trial)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "No prior Grade ≥3 mucositis from antifolates"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
