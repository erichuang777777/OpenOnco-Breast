# Migration draft — Adult granulosa cell tumor of the ovary (DIS-GRANULOSA-CELL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_granulosa_cell_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Advanced stage III–IV AGCT OR recurrent AGCT with rapid progression"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{any_of: [{finding: "stage_iii"}, {finding: "rapid_progression"}]}`
  - Candidate finding key(s): `stage_iii; rapid_progression`
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Recurrent hormone receptor-positive AGCT with slow progression"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
