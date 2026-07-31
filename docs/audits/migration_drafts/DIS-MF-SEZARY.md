# Migration draft — Mycosis Fungoides / Sézary Syndrome (DIS-MF-SEZARY)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_mf_sezary_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Best response to induction is CR or PR"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `pr_status`
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "Tolerating systemic therapy"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "Brentuximab vedotin not previously administered"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 3, MIXED_ALL): `condition: "Mogamulizumab not previously administered"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
