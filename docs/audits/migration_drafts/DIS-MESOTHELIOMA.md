# Migration draft — Malignant pleural mesothelioma (MPM) (DIS-MESOTHELIOMA)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_mesothelioma_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Unresectable MPM (multidisciplinary assessment: IMIG stage III-IV, bilateral disease, poor PS, or patient declines surgery)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Technical unresectability confirmed by thoracic surgery + MDT"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Non-epithelioid histology (sarcomatoid, desmoplastic, or biphasic with sarcomatoid component ≥50%)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "No active autoimmune disease requiring systemic treatment"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "active_autoimmune_disease"}`
  - Candidate finding key(s): `active_autoimmune_disease`
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "No solid organ transplant"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "No prior immune-mediated pneumonitis Grade ≥2"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
