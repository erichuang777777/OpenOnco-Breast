## Chunk Spec

chunks/openonco/algo-branch-wiring-esoph-metastatic-1l.md

## Chunk ID

algo-branch-wiring-esoph-metastatic-1l

## Topic Labels

mechanical-rewrite, engine-wiring, algorithm-branch

## Drop Estimate

~1 Drop (~100K tokens)

## Required Skill

plugins/openonco-contributor/skills/openonco-contribute/SKILL.md

## Branch Naming Convention

tasktorrent/algo-branch-wiring-esoph-metastatic-1l

## Sidecar Output Path

```
contributions/algo-branch-wiring-esoph-metastatic-1l/
```

## Task Manifest

Canonical source: `romeo111/OpenOnco` branch `master` at the latest commit when the volunteer claims this chunk.

The manifest is the set of free-text `condition:` strings inside `knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml.decision_tree`. Volunteer commits as:

```
contributions/algo-branch-wiring-esoph-metastatic-1l/task_manifest.txt
```

The chunk targets **5 currently-unreached indications** referenced from `algo_esoph_metastatic_1l.yaml.output_indications` — #3 on the backlog by unreached count per `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`.

## Mission

Translate every free-text `condition:` string in `ALGO-ESOPH-METASTATIC-1L`'s `decision_tree` into structured clauses keyed on existing patient-profile fields — histology (adenocarcinoma vs SCC: `disease_state.histology`), HER2 (`BIO-HER2-SOLID`), PD-L1 CPS (`BIO-PDL1-CPS`), MSI/dMMR (`BIO-MSI-STATUS`, `BIO-DMMR-IHC`), Claudin-18.2 (`BIO-CLDN18-2` if present).

**Worked example:** PR https://github.com/romeo111/cancer-autoresearch/pull/597.

**Do not change:** clinical content, biomarker definitions, regimen content, patient-profile schema. Pure semantics-preserving translation.

## Allowed Sources

Engine wiring only — no new source citations. Volunteer reads:

- `knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml`.
- The 5 target `IND-ESOPH-METASTATIC-1L-*` YAMLs.
- Existing esophageal `Biomarker` entities.
- Schemas + evaluator + PR #597 (as above).

## Disallowed Sources

OncoKB / SRC-ONCOKB, SNOMED CT, MedDRA.

## Input Context

- Source repo: `romeo111/cancer-autoresearch` branch `master`
- Algorithm path: `knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml`
- Worked example PR: https://github.com/romeo111/cancer-autoresearch/pull/597
- Backlog doc: `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch` from branch `tasktorrent/algo-branch-wiring-esoph-metastatic-1l`, modifying:

```
knowledge_base/hosted/content/algorithms/algo_esoph_metastatic_1l.yaml
examples/patient_verified_esoph_*.json
scripts/site_cases.py
```

Plus sidecar files in `contributions/algo-branch-wiring-esoph-metastatic-1l/`.

## Acceptance Criteria (machine-checkable)

- [ ] PR branch name matches `tasktorrent/algo-branch-wiring-esoph-metastatic-1l`.
- [ ] `task_manifest.txt` committed and enumerates every `condition:` translated.
- [ ] KB validator green (`--strict`).
- [ ] `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k esoph` passes.
- [ ] `scripts/audit_example_plan_coverage.py --algorithm ALGO-ESOPH-METASTATIC-1L` reports ≥ 3 of 5 unreached now reachable (≥ 5 target).
- [ ] Diff size ≤ 15 LOC inside the algorithm YAML.
- [ ] Diff confined to algorithm YAML + regenerated esoph example JSONs + `scripts/site_cases.py` auto-block + sidecar folder.
- [ ] `_contribution.ai_tool` + `_contribution.ai_model` present.

## Acceptance Criteria (semantic, maintainer-checked)

- [ ] Each translated condition preserves clinical intent.
- [ ] No regression in previously-reachable indications.
- [ ] Maintainer 100% read of translations.
- [ ] **No Clinical Co-Lead signoff required.**

## Rejection Criteria

- Translated condition wider/narrower than prose.
- New clinical clause invented.
- Diff touches engine/schema/non-allowlisted files.
- KB validator fails or pytest fails.
- Regression.
- New patient-profile field invented without surfacing first.
- Pre-commit hooks bypassed (`--no-verify`).
- `git add -A` / `git add .` evidence.
