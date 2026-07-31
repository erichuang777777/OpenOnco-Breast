# Migration draft — Primary Myelofibrosis (DIPSS-Plus stratified) (DIS-PMF)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_pmf_1l.yaml`

- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Default low / int-1 PMF; symptomatic management as needed"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_pmf_2l.yaml`

- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Default ruxolitinib-resistant non-anemic non-frail — fedratinib per JAKARTA-2"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
