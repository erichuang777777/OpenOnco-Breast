## Chunk Spec

chunks/openonco/algo-branch-wiring-ovarian-2l.md

## Chunk ID

algo-branch-wiring-ovarian-2l

## Topic Labels

mechanical-rewrite, engine-wiring, algorithm-branch

## Drop Estimate

~1 Drop (~100K tokens)

## Required Skill

plugins/openonco-contributor/skills/openonco-contribute/SKILL.md

## Branch Naming Convention

tasktorrent/algo-branch-wiring-ovarian-2l

## Sidecar Output Path

```
contributions/algo-branch-wiring-ovarian-2l/
```

## Task Manifest

Canonical source: `romeo111/OpenOnco` branch `master` at the latest commit when the volunteer claims this chunk.

The manifest is the set of free-text `condition:` strings inside `knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml.decision_tree`. The volunteer commits the enumeration as:

```
contributions/algo-branch-wiring-ovarian-2l/task_manifest.txt
```

Each row of the manifest is one `(step_index, condition_text)` pair extracted from the algorithm YAML. The chunk is out-of-manifest if a translation appears for a condition that does not exist in the algorithm YAML at the source commit.

The chunk targets **6 currently-unreached indications** referenced from `algo_ovarian_2l.yaml.output_indications`. Their exact IDs are extracted from the algorithm YAML at claim time.

## Mission

Translate every free-text `condition:` string in `ALGO-OVARIAN-2L`'s `decision_tree` into a structured clause (`{biomarker: BIO-*, value: positive|negative}` or `{finding: <patient-key>, comparator: <op>, threshold: <val>}`, with `any_of:` / `all_of:` wrappers as needed) so the engine actually walks the tree and the 6 currently-unreached indications become routable.

Per the state audit at `docs/reviews/openonco-state-audit-2026-05-17.md` §3, 85% of algorithm `condition:` strings are prose that `_eval_clause` silently treats as `False`; `ALGO-OVARIAN-2L` is the top algorithm by unreached-indication count (6).

**Worked example:** PR https://github.com/romeo111/cancer-autoresearch/pull/597 (`14062cdb6a`) translated `ALGO-AITL-2L` step 2. Same pattern applies here.

**Do not change:** indication semantics, biomarker definitions, regimen content, RT or surgery additions, patient-profile schema. Pure semantics-preserving translation only.

## Allowed Sources

This chunk is engine wiring, not clinical content — no new source citations introduced. Volunteer reads:

- `knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml` (canonical for what each prose condition means).
- The 6 target `IND-OVARIAN-2L-*` YAMLs (for biomarker-requirement field names).
- `knowledge_base/schemas/algorithm.py` and `knowledge_base/schemas/patient.py`.
- `knowledge_base/engine/redflag_eval.py` (`_eval_clause`).
- PR #597 in OpenOnco.

## Disallowed Sources

OncoKB / SRC-ONCOKB, SNOMED CT, MedDRA. Not relevant here — no source citations are introduced — but listed for completeness per OpenOnco pilot policy.

## Input Context

- Source repo: `romeo111/cancer-autoresearch` branch `master`
- Algorithm path: `knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml`
- Schema: `knowledge_base/schemas/algorithm.py`
- Evaluator: `knowledge_base/engine/redflag_eval.py`
- Worked example PR: https://github.com/romeo111/cancer-autoresearch/pull/597
- Backlog doc: `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch` from branch `tasktorrent/algo-branch-wiring-ovarian-2l`, modifying:

```
knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml
examples/patient_verified_ovarian_*.json
scripts/site_cases.py
```

Plus sidecar files:

```
contributions/algo-branch-wiring-ovarian-2l/task_manifest.txt
contributions/algo-branch-wiring-ovarian-2l/_contribution_meta.yaml
```

The PR body must include a before/after table of the 6 translated condition strings plus the output of `scripts/audit_example_plan_coverage.py --algorithm ALGO-OVARIAN-2L` (before and after).

## Acceptance Criteria (machine-checkable)

- [ ] PR branch name matches `tasktorrent/algo-branch-wiring-ovarian-2l`.
- [ ] `task_manifest.txt` is committed and enumerates every `condition:` translated.
- [ ] KB validator green: `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict`.
- [ ] Engine tests pass: `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k ovarian`.
- [ ] `scripts/audit_example_plan_coverage.py --algorithm ALGO-OVARIAN-2L` reports ≥ 3 of 6 previously-unreached indications now reachable (≥ 6 is the target).
- [ ] Diff size ≤ 15 LOC inside the algorithm YAML.
- [ ] Diff is confined to: the single algorithm YAML, regenerated `examples/patient_verified_ovarian_*.json`, `scripts/site_cases.py` auto-block (if any), and the sidecar folder. No changes to engine code, schema, indications, regimens, redflags, or biomarkers.
- [ ] `_contribution.ai_tool` and `_contribution.ai_model` present in the contribution-meta sidecar.

## Acceptance Criteria (semantic, maintainer-checked)

- [ ] Each of the 6 translated conditions preserves the clinical intent of the prose it replaces (no widening, no narrowing).
- [ ] No previously-reachable indication becomes unreachable.
- [ ] Maintainer 100% read of the 6 translations side-by-side with the original prose.
- [ ] **No Clinical Co-Lead signoff required** — this is a semantics-preserving wire-up, not new clinical content.

## Rejection Criteria

- A translated condition is wider or narrower than the prose it replaces.
- A new clinical clause is invented that wasn't in the prose.
- Diff touches engine code, schema, or any non-allowlisted file.
- KB validator fails or pytest fails.
- A previously-reachable indication becomes unreachable.
- A new patient-profile field is invented without surfacing to maintainer first.
- Pre-commit hooks bypassed (`--no-verify`).
- `git add -A` / `git add .` evidence.
