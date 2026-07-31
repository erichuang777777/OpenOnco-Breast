# Migration draft — Myelodysplastic Syndromes — Higher-Risk (IPSS-R high / very high; includes MDS-EB) (DIS-MDS-HR)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_mds_hr_2l.yaml`

- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Default post-HMA failure, transplant-ineligible — ven+aza off-label or clinical trial"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
