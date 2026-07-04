# DEAD-class prose-condition cleanup — candidate list, not applied

**Status: draft candidates only. No changes have been made to any file
under `knowledge_base/hosted/content/algorithms/`.**

Per `docs/reviews/fable-opinion.md` Phase 2, and per the user's decision
on 2026-07-04 to downgrade this from "safe enough to auto-apply" to
"needs the same draft-only treatment as Phase 3" after a real incident
(below). This document is the audit trail: what the tooling proposes,
why it isn't being applied automatically, and what a future reviewer
needs to verify before applying any of it.

## What happened

`scripts/audit_prose_conditions.py` (Phase 1) classified 100 of the 654
prose `condition:` clauses as `DEAD` — sitting inside an `any_of`
alongside a working sibling clause (`finding:`/`red_flag:`/non-prose
`condition:`), so the OR's result is already determined by the working
sibling regardless of what the dead clause resolves to.

`scripts/apply_dead_condition_cleanup.py` was built to remove exactly
those 100 clauses, verified via `clause_path` position (not text
matching — 14 (file, condition_text) pairs repeat the same string at
more than one position in the corpus, some DEAD and some not). A dry
run confirmed all 100 at their exact expected positions with zero
drift.

**It was applied for real, and immediately caused a real regression:**
removing `condition: "ESCC CPS >=1"` from
`algo_esoph_metastatic_1l.yaml` step 10 broke
`tests/test_esophageal_1l_algorithm.py::
test_escc_cps_positive_chemo_sparing_routes_to_ipi_nivo`.

## Root cause

`DEAD` proves the `any_of` has a working sibling *in the general case*.
It does not prove no caller ever resolves the prose text itself as a
literal finding key. `tests/test_esophageal_1l_algorithm.py` sets
`{"ESCC CPS >=1": True}` directly in its patient fixture — the exact
prose string, used as a workaround so the test passes despite the
underlying prose-condition bug (see
`docs/reviews/openonco-state-audit-2026-05-17.md`). Removing that
clause meant the patient no longer had *any* way to satisfy that
`any_of`, changing which indication the algorithm selected.

The routing-snapshot harness built for this phase
(`scripts/build_routing_snapshot.py`) uses two generic archetypes
("empty" and "all_true" over every real finding key in the tree) and
showed **zero diff** across all 360 rows after the cleanup — it did not
catch this, because neither generic archetype happens to set a literal
prose string as a finding key. Only the project's own hand-written test
suite caught it.

**Conclusion: a clean routing-snapshot diff alone is not sufficient
proof of safety for this class of change**, in this specific codebase,
because of the "prose text reused as a literal key" workaround pattern
already documented elsewhere in the repo.

## What was reverted

The full attempt — 100 clause removals across 41 files, plus the
`prose_condition_baseline.json` update reflecting the "improved" count
— was reverted in full (`git checkout --`) before anything was
committed or pushed. The current tree contains none of it. The 654/675
prose-condition baseline is unchanged from before this session's Phase
0 work.

## The candidate list (for future review, not auto-application)

`docs/audits/algorithm_condition_migration_queue.csv` (Phase 1 output,
committed) contains all 100 `DEAD`-classified rows alongside the other
554. A fresh dry run of the removal tool against the current tree
confirms:

```
$ python scripts/apply_dead_condition_cleanup.py --dry-run
...
[dry-run] 100 removed, 0 skipped
```

100/100 candidates still resolve to their exact expected YAML position
with zero drift.

## Verification run attached (baseline, current unmodified tree)

```
$ python -m pytest \
  tests/test_audit_validator_contracts.py \
  tests/test_run_scheduled_audit.py \
  tests/test_audit_writers.py \
  tests/test_algorithm_regimen_routing_contracts.py \
  tests/test_legacy_regimen_normalization.py \
  tests/test_esophageal_1l_algorithm.py \
  tests/test_check_prose_conditions.py \
  tests/test_audit_prose_conditions.py \
  tests/test_algorithm_routing_snapshot.py \
  -q
77 passed in 77.93s
```

All green against the current, unmodified tree — this is the baseline
a future application attempt must not regress.

## What a future reviewer/session must do before applying any of this

1. **Do not trust the routing-snapshot diff alone.** It is necessary
   but not sufficient — see root cause above.
2. **Run the full existing test suite** (not the CI subset above — all
   of `tests/`, or at minimum every test file that constructs a patient
   fixture referencing any of the 100 candidate files' algorithm IDs)
   after each file's edit, or more conservatively after each individual
   clause removal, and revert immediately on any failure.
3. **Grep the candidate's exact condition text against the whole test
   suite and `examples/*.json`** before removing it — if any fixture
   sets that literal string as a finding key (the ESCC CPS pattern),
   treat the clause as NOT dead regardless of what the structural
   classifier says, and route it through the same Phase 3
   clinical-review process as the other 554.
4. Only after (1)-(3) clear for every candidate should this be
   considered for actual application — and per CHARTER §6.1, any change
   under `knowledge_base/hosted/content/` still needs a human decision
   on whether that gate applies even to a "provably inert" cleanup (the
   user's 2026-07-04 answer was: treat it the same as Phase 3, draft
   only, no auto-apply).

## Sign-off

- **Author:** claude (this session)
- **Date:** 2026-07-04
- **Decision:** user-confirmed downgrade to draft-only treatment after
  the incident above. No knowledge_base content changed as a result of
  this work.
