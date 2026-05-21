## Chunk Spec

chunks/openonco/algo-branch-wiring-breast-1l.md

## Chunk ID

algo-branch-wiring-breast-1l

## Topic Labels

mechanical-rewrite, engine-wiring, algorithm-branch

## Drop Estimate

~1 Drop (~100K tokens)

## Required Skill

plugins/openonco-contributor/skills/openonco-contribute/SKILL.md

## Branch Naming Convention

tasktorrent/algo-branch-wiring-breast-1l

## Sidecar Output Path

```
contributions/algo-branch-wiring-breast-1l/
```

## Task Manifest

Canonical source: `romeo111/OpenOnco` branch `master` at the latest commit when the volunteer claims this chunk.

The manifest is the set of free-text `condition:` strings inside `knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml.decision_tree`. Volunteer commits the enumeration as:

```
contributions/algo-branch-wiring-breast-1l/task_manifest.txt
```

The chunk targets **5 currently-unreached indications** referenced from `algo_breast_1l.yaml.output_indications` — #2 on the backlog by unreached count per `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`.

## Mission

Translate every free-text `condition:` string in `ALGO-BREAST-1L`'s `decision_tree` into a structured clause keyed on existing patient-profile fields — hormone-receptor status (`BIO-ESTROGEN-RECEPTOR`, `BIO-PROGESTERONE-RECEPTOR`), HER2 (`BIO-HER2-SOLID`, `BIO-HER2-AMP`), BRCA germline (`BIO-BRCA1`, `BIO-BRCA2`), node status, menopausal status, prior endocrine exposure — so the engine actually walks the tree and the 5 currently-unreached indications become routable.

**Worked example:** PR https://github.com/romeo111/cancer-autoresearch/pull/597. Same pattern.

**Do not change:** indication semantics, biomarker definitions, regimen content, patient-profile schema. Pure semantics-preserving translation only.

## Allowed Sources

Engine wiring, not clinical content — no new source citations introduced. Volunteer reads:

- `knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml`.
- The 5 target `IND-BREAST-1L-*` YAMLs.
- Existing breast `Biomarker` entities under `knowledge_base/hosted/content/biomarkers/`.
- `knowledge_base/schemas/algorithm.py`, `knowledge_base/schemas/patient.py`, `knowledge_base/engine/redflag_eval.py`.
- PR #597 in OpenOnco.

## Disallowed Sources

OncoKB / SRC-ONCOKB, SNOMED CT, MedDRA.

## Input Context

- Source repo: `romeo111/cancer-autoresearch` branch `master`
- Algorithm path: `knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml`
- Worked example PR: https://github.com/romeo111/cancer-autoresearch/pull/597
- Backlog doc: `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch` from branch `tasktorrent/algo-branch-wiring-breast-1l`, modifying:

```
knowledge_base/hosted/content/algorithms/algo_breast_1l.yaml
examples/patient_verified_breast_*.json
scripts/site_cases.py
```

Plus sidecar files:

```
contributions/algo-branch-wiring-breast-1l/task_manifest.txt
contributions/algo-branch-wiring-breast-1l/_contribution_meta.yaml
```

## Acceptance Criteria (machine-checkable)

- [ ] PR branch name matches `tasktorrent/algo-branch-wiring-breast-1l`.
- [ ] `task_manifest.txt` is committed and enumerates every `condition:` translated.
- [ ] KB validator green (`--strict`).
- [ ] Engine tests pass: `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k breast`.
- [ ] `scripts/audit_example_plan_coverage.py --algorithm ALGO-BREAST-1L` reports ≥ 3 of 5 previously-unreached indications now reachable (≥ 5 target).
- [ ] Diff size ≤ 15 LOC inside the algorithm YAML.
- [ ] Diff is confined to: the algorithm YAML, regenerated breast example JSONs, `scripts/site_cases.py` auto-block (if any), and the sidecar folder.
- [ ] `_contribution.ai_tool` and `_contribution.ai_model` present.

## Acceptance Criteria (semantic, maintainer-checked)

- [ ] Each translated condition preserves clinical intent (no widening, no narrowing).
- [ ] No previously-reachable indication becomes unreachable.
- [ ] Maintainer 100% read of translations.
- [ ] **No Clinical Co-Lead signoff required.**

## Rejection Criteria

- Translated condition wider/narrower than prose.
- New clinical clause invented.
- Diff touches engine/schema/non-allowlisted files.
- KB validator fails or pytest fails.
- Regression (previously-reachable indications become unreachable).
- New patient-profile field invented without surfacing first.
- Pre-commit hooks bypassed (`--no-verify`).
- `git add -A` / `git add .` evidence.
