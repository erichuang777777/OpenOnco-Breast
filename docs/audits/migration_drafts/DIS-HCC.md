# Migration draft — Hepatocellular carcinoma (HCC) (DIS-HCC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_hcc_systemic_2l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Prior 1L was TKI-based (sorafenib OR lenvatinib monotherapy)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Sorafenib was tolerated in 1L (≥21 days at ≥400 mg/d, stopped for progression not toxicity)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Child-Pugh A AND ECOG 0-1 AND no prior TKI in 1L"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `ecog_status`
