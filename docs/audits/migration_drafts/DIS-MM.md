# Migration draft — Multiple Myeloma (DIS-MM)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_mm_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Post-ASCT (autoSCT consolidation completed)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "Disease status: CR, VGPR, or PR"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `pr_status`
- **`all_of[2]`** (step 1, SOLE_ALL): `condition: "No active progression"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "≥3 prior lines including ≥1 IMiD, ≥1 PI, ≥1 anti-CD38"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "Triple-class refractory (refractory to last line of each class)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "triple_class_refractory"}`
  - Candidate finding key(s): `triple_class_refractory`
- **`all_of[3]`** (step 2, MIXED_ALL): `condition: "adequate organ function for bispecific"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_mm_3l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "≥3 prior lines including ≥1 IMiD, ≥1 PI, ≥1 anti-CD38 monoclonal antibody"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "Refractory (progressed during or within 60 days of last line of each class)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "Carfilzomib-naive (no prior carfilzomib or carfilzomib-based regimen)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "≥2 prior lines including ≥1 PI (non-carfilzomib) + ≥1 IMiD"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
