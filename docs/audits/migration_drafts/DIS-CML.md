# Migration draft — Chronic Myeloid Leukemia (BCR-ABL1) (DIS-CML)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_cml_1l.yaml`

- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Default low-risk CML chronic phase (negative for Sokal-high / Hasford-high gated above)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_cml_2l.yaml`

- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Default 2L+ CML, T315I-negative, non-blast — asciminib preferred over 2GTKI recycle"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
