## Chunk Spec

chunks/openonco/prevention-regimen-authoring-wave1.md

## Chunk ID

prevention-regimen-authoring-wave1

## Topic Labels

evidence-draft, coverage-gap, prevention

## Drop Estimate

~2-3 Drops (~250K tokens)

## Required Skill

plugins/openonco-contributor/skills/openonco-contribute/SKILL.md

## Branch Naming Convention

tasktorrent/prevention-regimen-authoring-wave1

## Sidecar Output Path

```
contributions/prevention-regimen-authoring-wave1/
```

## Task Manifest

Canonical source: `romeo111/OpenOnco` branch `master` at the latest commit when the volunteer claims this chunk.

The manifest is fixed for this wave — 6 named Regimen entities to author:

```
contributions/prevention-regimen-authoring-wave1/task_manifest.txt
```

```
REG-HP-BISMUTH-QUADRUPLE
REG-HP-PPI-CLAR-AMOX-TRIPLE
REG-HBV-ENTECAVIR
REG-HBV-TENOFOVIR-AF
REG-HPV-GARDASIL-9
REG-HIV-BICTARVY
```

All 9 referenced drug entities (`DRUG-BISMUTH-SUBCITRATE`, `DRUG-TETRACYCLINE`, `DRUG-METRONIDAZOLE`, `DRUG-OMEPRAZOLE`, `DRUG-CLARITHROMYCIN`, `DRUG-AMOXICILLIN`, `DRUG-ENTECAVIR`, `DRUG-TENOFOVIR-AF`, `DRUG-GARDASIL-9`, `DRUG-BICTEGRAVIR-EMTRICITABINE-TAF`) already exist (v0.2-A commit `1eb3addfe8`). All 7 cited sources already exist (commit `a66f47760b`). Exact drug-ID spelling confirmed when the volunteer claims this chunk.

## Mission

Author 6 prevention `Regimen` YAMLs whose drug entities are already in the KB and whose cited sources are already in the KB, so that the existing prevention indications referencing these regimen IDs can replace their `recommended_regimen: null` placeholders.

Per the OpenOnco v0.2-A authoring backlog (`docs/reviews/volunteer-shortlist-2026-05-20.md` §1.1), prevention indications currently exist but carry `recommended_regimen: null` because the regimen entities have not been authored. This chunk closes that gap for the 6 most-cited regimens.

Dosing strings must be source-verbatim from `SRC-AASLD-HBV-2024`, `SRC-AASLD-IDSA-HCV-2023`, `SRC-AGA-H-PYLORI-2024`, `SRC-ACG-H-PYLORI-2024`, `SRC-IARC-MONOGRAPH-100B-2012`, plus DHHS/NIH HIV ART source (confirm exact SRC-ID at claim time). Do NOT paraphrase dosing.

**Do not change:** the indications referencing these regimens; existing drug entities; existing sources. Pure additive — 6 new YAMLs.

## Allowed Sources

All in repo:

- `SRC-AASLD-HBV-2024`
- `SRC-AASLD-IDSA-HCV-2023`
- `SRC-AGA-H-PYLORI-2024`
- `SRC-ACG-H-PYLORI-2024`
- `SRC-IARC-MONOGRAPH-100B-2012`
- DHHS / NIH HIV ART source (`SRC-NIH-AIDS` or `SRC-DHHS-HIV-202X` — confirm at claim time)
- DailyMed / openFDA per-drug package inserts (verbatim dose extraction reference)

## Disallowed Sources

OncoKB / SRC-ONCOKB, SNOMED CT, MedDRA.

## Input Context

- Source repo: `romeo111/cancer-autoresearch` branch `master`
- Schema: `knowledge_base/schemas/regimen.py` (note `phases` field per KSS §17)
- Existing prevention regimen template: `knowledge_base/hosted/content/regimens/reg_tamoxifen_chemoprevention.yaml`
- v0.2-A roadmap entry: `docs/plans/openonco_prevention_scope_2026-05-18-1500.md`
- KSS §20 (prevention schema additions): `specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md`

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch` from branch `tasktorrent/prevention-regimen-authoring-wave1`, creating:

```
knowledge_base/hosted/content/regimens/reg_hp_bismuth_quadruple.yaml
knowledge_base/hosted/content/regimens/reg_hp_ppi_clar_amox_triple.yaml
knowledge_base/hosted/content/regimens/reg_hbv_entecavir.yaml
knowledge_base/hosted/content/regimens/reg_hbv_tenofovir_af.yaml
knowledge_base/hosted/content/regimens/reg_hpv_gardasil_9.yaml
knowledge_base/hosted/content/regimens/reg_hiv_bictarvy.yaml
```

Plus sidecar files:

```
contributions/prevention-regimen-authoring-wave1/task_manifest.txt
contributions/prevention-regimen-authoring-wave1/_contribution_meta.yaml
```

The PR body must list each regimen with its cited source + verbatim dose-snippet.

## Acceptance Criteria (machine-checkable)

- [ ] PR branch name matches `tasktorrent/prevention-regimen-authoring-wave1`.
- [ ] All 6 regimen YAMLs created.
- [ ] All 6 reference real `DRUG-*` IDs that resolve.
- [ ] All `evidence_sources` reference real `SRC-*` IDs that resolve.
- [ ] All 6 carry `intent: prevention`.
- [ ] All 6 carry `draft: true` and `_contribution.ai_tool` + `_contribution.ai_model`.
- [ ] KB validator green: `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict`.
- [ ] All 6 regimens are reachable from ≥1 prevention Indication each (cross-reference check).
- [ ] `pytest tests/test_prevention_render.py tests/test_prevention_engine.py` green.

## Acceptance Criteria (semantic, maintainer-checked)

- [ ] Maintainer 100% read; 2-of-6 source-PDF spot-check confirms dosing strings are verbatim, not paraphrased.
- [ ] Clinical Co-Lead 1 of 3 sample-check (CHARTER §6.1 dev-mode exemption) confirms dose schedules match standard-of-care for immunocompetent adult.

## Rejection Criteria

- Dosing strings paraphrased rather than source-verbatim.
- Drug entity references that don't resolve.
- Source citations that don't resolve.
- `intent:` field missing or set to `treatment`.
- Treatment-recommendation language in `notes:` or `rationale:` (CHARTER §8.3).
- Invented dose schedule not attested in cited source.
- Use of OncoKB / SNOMED CT / MedDRA in any citation.
- Pre-commit hooks bypassed (`--no-verify`).
- `git add -A` / `git add .` evidence.
