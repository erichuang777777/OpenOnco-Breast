# algo-branch-wiring-breast-1l

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
`finding:` clauses in `ALGO-BREAST-1L`. Same shape as the
`algo-branch-wiring-ovarian-2l` chunk (see Notes).

## Queue
`A`

## Min Contributor Tier
`new`

## Severity
`low`

## Topic Labels
`mechanical-rewrite`, `engine-wiring`, `algorithm-branch`

## Mission

Wire `ALGO-BREAST-1L` so the **5 currently-unreached `IND-*`
entries** referenced from its decision tree become routable.

Per [docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md),
`ALGO-BREAST-1L` is **#2 on the backlog** by unreached-indication
count (5). Its `decision_tree` uses free-text `condition:` strings
that the engine's `_eval_clause` silently treats as `False`. Every
synthetic patient falls through to `default_indication`.

**Translation pattern (PR [#597](https://github.com/romeo111/cancer-autoresearch/pull/597)
worked example):** replace each free-text `condition:` with a
structured clause keyed on existing patient-profile fields —
hormone-receptor status (`BIO-ESTROGEN-RECEPTOR`,
`BIO-PROGESTERONE-RECEPTOR`), HER2 status (`BIO-HER2-SOLID`,
`BIO-HER2-AMP`), BRCA germline (`BIO-BRCA1`, `BIO-BRCA2`), node
status, menopausal status, prior endocrine exposure.

**Scope of this single chunk:** ONE algorithm (`ALGO-BREAST-1L`).
50 remaining algorithms with prose conditions stay on the backlog
for follow-up chunks of identical shape.

**KB coverage:** Advances `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`
— 2 of 52 algorithms now wired (after the ovarian chunk lands);
5 of 89 unreached indications made reachable.

**Out of scope:** authoring new `Indication`, `Regimen`, or `RF`
entities; introducing new patient-profile fields; resolving
clinical-evidence disagreements; RT or surgery additions per
CHARTER §17.

## Drop Estimate

~1 Drop (~100K tokens). One algorithm read, ≤5 condition strings
translated, ≤5-line YAML diff, golden-test snapshot update, example
patient JSON regenerated.

## Required Skill

`openonco-contributor:openonco-contribute`. Same knowledge profile
as `algo-branch-wiring-ovarian-2l` — read the schema in
[knowledge_base/schemas/algorithm.py](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/schemas/algorithm.py),
the evaluator in
[knowledge_base/engine/redflag_eval.py](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/engine/redflag_eval.py),
and PR [#597](https://github.com/romeo111/cancer-autoresearch/pull/597)
end-to-end. No clinical authoring required.

## Allowed Sources

Engine wiring, not clinical content — no new source citations
introduced. Volunteer reads:

- `knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml`
  (canonical for what each prose condition means).
- The 5 target `IND-BREAST-1L-*` YAMLs referenced from the algorithm.
- Existing breast `Biomarker` entities under
  `knowledge_base/hosted/content/biomarkers/`.

**Banned per OpenOnco pilot:** OncoKB, SNOMED CT, MedDRA. Not
relevant here.

## Manifest

| Field | Value |
|---|---|
| `algorithm_id` | `ALGO-BREAST-1L` |
| `algorithm_yaml_path` | `knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml` |
| `unreached_indications` | 5 (exact ids enumerated when chunk-task issue opens) |
| `expected_diff_size_loc` | ≤ 15 lines |
| `validator_command` | `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| `reachability_command` | `python scripts/audit_example_plan_coverage.py --algorithm ALGO-BREAST-1L` |
| `golden_test_command` | `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k breast` |
| `worked_example_pr` | https://github.com/romeo111/cancer-autoresearch/pull/597 |

## Computation

Same 6-step pattern as `algo-branch-wiring-ovarian-2l`:

1. Identify the clinical concept each prose `condition:` names.
2. Locate the matching patient-profile field via
   [knowledge_base/schemas/patient.py](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/schemas/patient.py)
   and the target indications' `applicable_to.biomarker_requirements_*`.
3. Translate to `{biomarker: <BIO-ID>, value: positive|negative}`
   or `{finding: <key>, comparator: <op>, threshold: <val>}`, with
   `any_of:` / `all_of:` wrappers as needed.
4. Re-run validator + reachability + golden tests. All green.
5. Regenerate verified-treatment-example patient JSONs.
6. Open PR. Branch: `feat/algo-breast-1l-wire-2026-05-20-HHMM`.

Stop and surface if a prose condition cannot be translated 1:1.

## Where computation happens

Contributor's machine. Python 3.12; `git clone
https://github.com/romeo111/cancer-autoresearch`; PR against
`master`.

## Re-verification

### Pre-acceptance gates (auto-reject)

- KB validator green (`--strict`).
- `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k breast`
  pass.
- `scripts/audit_example_plan_coverage.py --algorithm ALGO-BREAST-1L`
  reports ≥ 3 of 5 previously-unreached indications now reachable
  (≥ 5 is the target).
- Diff size ≤ 15 LOC inside the algorithm YAML.
- Diff confined to
  `knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml` +
  generated verified-treatment-example JSONs +
  `scripts/site_cases.py` auto-block (if any). NO changes to
  engine code, schema, indications, regimens, redflags, biomarkers.
- `_contribution.ai_tool` and `_contribution.ai_model` present.

### Computational re-verify

`python scripts/audit_example_plan_coverage.py --algorithm
ALGO-BREAST-1L --before <baseline-sha> --after <pr-head-sha>` must
show strict improvement, no regressions.

### Sample human re-verify

Maintainer (1 person): read each condition translation side-by-side
against the prose. 100% read — only 5 clauses.

**No Clinical Co-Lead signoff required** (semantics-preserving
translation).

### Trust threshold

1 of 1 maintainer review. Auto-merge to `master` once gates green.

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch`,
branch `feat/algo-breast-1l-wire-2026-05-20-HHMM`, modifying:

```
knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml
examples/patient_verified_breast_*.json
scripts/site_cases.py
```

Plus contribution-meta sidecar.

## Acceptance Criteria

- All pre-acceptance gates pass.
- Maintainer sample-review confirms 5 condition translations
  preserve clinical intent.
- ≥ 3 of 5 unreached indications now reachable (≥ 5 is target).
- PR diff confined to the file allowlist.

## Rejection Criteria

- Translated condition wider/narrower than prose.
- New clinical clause invented.
- Diff touches engine/schema/non-allowlisted files.
- KB validator fails.
- Regression (previously-reachable indications now unreachable).
- New patient-profile fields invented without surfacing first.

## Claim Method

`trusted-agent-wip-branch-first`. Volunteer opens `[Chunk]
algo-branch-wiring-breast-1l` issue against `romeo111/task_torrent`;
pushes WIP branch within 24 h; opens PR within 5 working days.

## Reviewer

- Maintainer: 1.
- Clinical Co-Lead signoff: not required.

## Notes

Second chunk in the **52-algorithm algorithm-branch-wiring family**.
Identical shape to `algo-branch-wiring-ovarian-2l`; only the disease
+ algorithm + test-filter swap. Maintainer-only effort to spin up the
remaining 50 chunks: ~15 minutes each.

After this lands, the next-priority spin-ups by unreached count:

- `algo-branch-wiring-esoph-metastatic-1l` (5) — drafted in this
  same wave.
- `algo-branch-wiring-cervical-metastatic-1l` (4)
- `algo-branch-wiring-aitl-2l` (already wired by PR #597 — skip)

The Big-P3 alternative (structured-condition AST migration) is
documented in
[docs/reviews/openonco-state-audit-2026-05-17.md §3 path 2](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/reviews/openonco-state-audit-2026-05-17.md);
out of scope for volunteer chunks.
