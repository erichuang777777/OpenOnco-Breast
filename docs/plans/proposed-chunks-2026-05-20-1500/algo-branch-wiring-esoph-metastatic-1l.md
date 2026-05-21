# algo-branch-wiring-esoph-metastatic-1l

## Status
`queued`

## Economic Profile
```yaml
compute_profile: low
verification_method: deterministic
break_even_test: PASS
output_type: kb-yaml-edit
backfilled_retroactively: false
```

Mechanical translation of prose `condition:` strings to structured
`finding:` clauses in `ALGO-ESOPH-METASTATIC-1L`.

## Queue
`A`

## Min Contributor Tier
`new`

## Severity
`low`

## Topic Labels
`mechanical-rewrite`, `engine-wiring`, `algorithm-branch`

## Mission

Wire `ALGO-ESOPH-METASTATIC-1L` so the **5 currently-unreached
`IND-*` entries** referenced from its decision tree become routable.

Per [docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md),
`ALGO-ESOPH-METASTATIC-1L` is **#3 on the backlog** by unreached-
indication count (5).

**Translation pattern (PR [#597](https://github.com/romeo111/cancer-autoresearch/pull/597)
worked example):** replace each free-text `condition:` with a
structured clause keyed on existing patient-profile fields — histology
(adenocarcinoma vs SCC: `disease_state.histology`), HER2 status
(`BIO-HER2-SOLID`), PD-L1 CPS (`BIO-PDL1-CPS`), MSI/dMMR
(`BIO-MSI-STATUS`, `BIO-DMMR-IHC`), Claudin-18.2 (`BIO-CLDN18-2` if
present in repo).

**Scope:** ONE algorithm. 50 remaining algorithms stay on backlog.

**KB coverage:** 3 of 52 algorithms wired (after ovarian + breast
land); 5 of 89 unreached indications made reachable.

**Out of scope:** new clinical content, new patient-profile fields,
RT or surgery additions.

## Drop Estimate

~1 Drop (~100K tokens).

## Required Skill

`openonco-contributor:openonco-contribute`. Same knowledge profile
as `algo-branch-wiring-ovarian-2l`. Read PR
[#597](https://github.com/romeo111/cancer-autoresearch/pull/597)
end-to-end.

## Allowed Sources

Engine wiring, not clinical content — no new source citations
introduced. Volunteer reads:

- `knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml`.
- The 5 target `IND-ESOPH-METASTATIC-1L-*` YAMLs.
- Existing esophageal `Biomarker` entities.

**Banned per OpenOnco pilot:** OncoKB, SNOMED CT, MedDRA.

## Manifest

| Field | Value |
|---|---|
| `algorithm_id` | `ALGO-ESOPH-METASTATIC-1L` |
| `algorithm_yaml_path` | `knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml` |
| `unreached_indications` | 5 |
| `expected_diff_size_loc` | ≤ 15 lines |
| `validator_command` | `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| `reachability_command` | `python scripts/audit_example_plan_coverage.py --algorithm ALGO-ESOPH-METASTATIC-1L` |
| `golden_test_command` | `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k esoph` |
| `worked_example_pr` | https://github.com/romeo111/cancer-autoresearch/pull/597 |

## Computation

Same 6-step pattern as `algo-branch-wiring-ovarian-2l`. Stop and
surface if a prose condition cannot be translated 1:1.

## Where computation happens

Contributor's machine. Python 3.12; `git clone
https://github.com/romeo111/cancer-autoresearch`; PR against
`master`.

## Re-verification

### Pre-acceptance gates

- KB validator green (`--strict`).
- `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k esoph`
  pass.
- `audit_example_plan_coverage.py` reports ≥ 3 of 5 unreached now
  reachable (≥ 5 target).
- Diff size ≤ 15 LOC.
- Diff confined to allowlist (algorithm YAML + generated example
  JSONs + `scripts/site_cases.py` auto-block).
- `_contribution.ai_tool` + `_contribution.ai_model` present.

### Computational re-verify

`audit_example_plan_coverage.py --before ... --after ...` shows
strict improvement, no regression.

### Sample human re-verify

Maintainer: 100% read of 5 translations.

**No Clinical Co-Lead signoff** (semantics-preserving).

### Trust threshold

1 of 1 maintainer review. Auto-merge once gates green.

## Output Format

Single PR, branch `feat/algo-esoph-metastatic-1l-wire-2026-05-20-HHMM`,
modifying:

```
knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml
examples/patient_verified_esoph_*.json
scripts/site_cases.py
```

## Acceptance Criteria

- All gates pass.
- 5-translation maintainer read.
- ≥ 3 of 5 reachable (≥ 5 target).
- Diff confined to allowlist.

## Rejection Criteria

- Wider/narrower translation.
- Invented clinical clause.
- Diff touches engine/schema/non-allowlisted files.
- Validator fails.
- Regression.
- New patient-profile field without surfacing first.

## Claim Method

`trusted-agent-wip-branch-first`. Volunteer opens `[Chunk]
algo-branch-wiring-esoph-metastatic-1l` issue against
`romeo111/task_torrent`.

## Reviewer

- Maintainer: 1.
- Clinical Co-Lead signoff: not required.

## Notes

Third chunk in the **52-algorithm algorithm-branch-wiring family**.
Identical shape to the ovarian + breast specs. After this lands the
next priority is `algo-branch-wiring-cervical-metastatic-1l` (4
unreached).
