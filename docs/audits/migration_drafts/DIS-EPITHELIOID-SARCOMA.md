# Migration draft — Epithelioid sarcoma (DIS-EPITHELIOID-SARCOMA)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_epithelioid_sarcoma_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "SMARCB1/INI1 loss confirmed by IHC"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
