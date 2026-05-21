## Chunk Spec

chunks/openonco/hereditary-brca-carrier-surveillance.md

## Chunk ID

hereditary-brca-carrier-surveillance

## Topic Labels

evidence-draft, coverage-gap, prevention, hereditary

## Drop Estimate

~1.5 Drops (~150K tokens)

## Required Skill

plugins/openonco-contributor/skills/openonco-contribute/SKILL.md
plus plugins/openonco-contributor/skills/biomarker-sidecar-draft/SKILL.md (for the carrier RF triggered by a Biomarker positive result)

## Branch Naming Convention

tasktorrent/hereditary-brca-carrier-surveillance

## Sidecar Output Path

```
contributions/hereditary-brca-carrier-surveillance/
```

## Task Manifest

Canonical source: `romeo111/OpenOnco` branch `master` at the latest commit when the volunteer claims this chunk.

The manifest is fixed: 1 RedFlag + 2 Indications to author.

```
contributions/hereditary-brca-carrier-surveillance/task_manifest.txt
```

```
RF-BRCA-CONFIRMED-CARRIER
IND-BRCA-CARRIER-ENHANCED-SURVEILLANCE
IND-BRCA-CARRIER-RISK-REDUCTION
```

Existing entities the new ones reference (all already in repo): `BIO-BRCA1`, `BIO-BRCA2`, `DIS-BREAST`, `DIS-OVARIAN`, `DIS-PROSTATE`, `DIS-PDAC`, `DIS-MELANOMA`, `SRC-NCCN-GENETIC-FAMILIAL-BREAST-OVARIAN-2025`, `SRC-ASCO-ACMG-LYNCH-2014`, `RF-BRCA-HBOC-FAMILY-HISTORY-SUSPICION` (pre-testing RF, continues to coexist).

## Mission

Author the post-test-positive surveillance pathway for confirmed BRCA1/2 germline carriers — closes the v0.2-B continuation gap explicitly listed in the OpenOnco roadmap:

> Pending v0.2-B continuation: confirmed-carrier surveillance pathways (RF-*-CONFIRMED-CARRIER + IND-*-CARRIER-SURVEILLANCE post-test-positive).

The v0.2-B pilot (commit `f252a24e5d`) shipped the pedigree-suspicion RF + the genetic-counseling / decline-testing tracks for BRCA / HBOC but stopped short of the post-test-positive pathway. This chunk closes it.

| Entity | Purpose |
|---|---|
| `RF-BRCA-CONFIRMED-CARRIER` | Fires on positive germline BRCA1/2 result (`BIO-BRCA1: positive` OR `BIO-BRCA2: positive`). `risk_category: hereditary` (KSS §20.4). |
| `IND-BRCA-CARRIER-ENHANCED-SURVEILLANCE` | Standard track — annual breast MRI + mammography starting age 25-30, semi-annual clinical breast exam, TVUS + CA-125 every 6 months until RRSO, RRSO discussion age 35-40 (BRCA1) / 40-45 (BRCA2). |
| `IND-BRCA-CARRIER-RISK-REDUCTION` | Alternative track per CHARTER §15.2 C4 — risk-reducing mastectomy + RRSO via shared-decision-making framework. |

The existing `RF-BRCA-HBOC-FAMILY-HISTORY-SUSPICION` continues to fire pre-testing; the new `RF-BRCA-CONFIRMED-CARRIER` takes over post-result. Both coexist (graceful handoff).

**Cross-etiology isolation:** Lynch + VHL + HLRCC carriers must NOT accidentally pick up BRCA surveillance — use the `triggered_by_redflags` engine guard added 2026-05-18. Test must verify this.

**Do not change:** existing pre-testing RF and indications; existing BRCA BMA cells; existing cascade-testing algorithms; existing source entities.

## Allowed Sources

- `SRC-NCCN-GENETIC-FAMILIAL-BREAST-OVARIAN-2025` (already in repo; **`legal_review.status: escalated`** per scope-proposal Q7 — if the legal review resolves against this source by claim time, fall back to USPSTF + ASCO-ACMG primary attribution).
- `SRC-ASCO-ACMG-LYNCH-2014` (already in repo; useful for cascade-testing precedent language).
- USPSTF Grade B recommendations on BRCA risk assessment (cite via primary `SRC-USPSTF-BRCA-202X` if it exists in repo; otherwise flag for `source-stub-ingest-batch` follow-up).
- ESMO + NICE — cite via existing repo `SRC-*` if present; otherwise flag.

## Disallowed Sources

OncoKB / SRC-ONCOKB, SNOMED CT, MedDRA.

## Input Context

- Source repo: `romeo111/cancer-autoresearch` branch `master`
- Sibling pre-testing RF: `knowledge_base/hosted/content/redflags/rf_brca_hboc_family_history_suspicion.yaml`
- Sibling pre-testing indications: `knowledge_base/hosted/content/indications/ind_brca_hboc_suspicion_prevention_*.yaml`
- Lynch starter (cross-etiology isolation precedent): commit `8e1b05e43f`
- Schemas: `knowledge_base/schemas/redflag.py`, `knowledge_base/schemas/indication.py`
- v0.2-B scope proposal: `docs/plans/openonco_prevention_scope_2026-05-18-1500.md`
- KSS §20.4 (new schema fields): `specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md`

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch` from branch `tasktorrent/hereditary-brca-carrier-surveillance`, creating:

```
knowledge_base/hosted/content/redflags/rf_brca_confirmed_carrier.yaml
knowledge_base/hosted/content/indications/ind_brca_carrier_enhanced_surveillance.yaml
knowledge_base/hosted/content/indications/ind_brca_carrier_risk_reduction.yaml
tests/test_prevention_engine.py    # add one new cross-etiology isolation test
```

Plus sidecar files:

```
contributions/hereditary-brca-carrier-surveillance/task_manifest.txt
contributions/hereditary-brca-carrier-surveillance/_contribution_meta.yaml
```

PR body must include the NCCN-Genetic-Familial section locator for the surveillance schedule + BRCA1 vs BRCA2 age thresholds + RRSO timing, plus cross-etiology isolation test output (Lynch + VHL + HLRCC patient profiles confirm they do NOT trigger BRCA carrier surveillance).

## Acceptance Criteria (machine-checkable)

- [ ] PR branch name matches `tasktorrent/hereditary-brca-carrier-surveillance`.
- [ ] 3 new entities (1 RF + 2 Indications) all reference real `BIO-*`, `DIS-*`, `SRC-*` IDs that resolve.
- [ ] All 3 carry `draft: true` and `_contribution.ai_tool` + `_contribution.ai_model`.
- [ ] RF carries `risk_category: hereditary` per KSS §20.4.
- [ ] Both Indications carry `intent: prevention` per KSS §20.4 and `triggered_by_redflags: [RF-BRCA-CONFIRMED-CARRIER]`.
- [ ] Engine cross-etiology isolation guard test passes: `pytest tests/test_prevention_engine.py::test_brca_carrier_does_not_trigger_lynch_surveillance` (the new test the volunteer authors).
- [ ] ≥ 2 source citations on the RF (publication gate).
- [ ] KB validator green (`--strict`).
- [ ] `pytest tests/test_prevention_engine.py -k brca` green.
- [ ] Diff size ≤ 250 LOC.

## Acceptance Criteria (semantic, maintainer-checked)

- [ ] Maintainer 100% read confirms cross-etiology isolation matches the Lynch sibling.
- [ ] Source citations resolve; no treatment-recommendation language anywhere.
- [ ] Clinical Co-Lead 1 of 3 sample-check (CHARTER §6.1 dev-mode exemption) confirms surveillance schedule matches NCCN-GENETIC-FAMILIAL standard for BRCA1 vs BRCA2 (age thresholds differ; capture honestly).
- [ ] Risk-reduction track is presented as a discussion, not a recommendation (CHARTER §8.3).

## Rejection Criteria

- Treatment-recommendation language ("you should have RRSO at age 38", etc.) anywhere in `rationale` or `notes`.
- Single-track output (CHARTER §15.2 C4 requires ≥2 tracks).
- Source citations that don't resolve.
- Use of OncoKB / SNOMED CT / MedDRA in any citation.
- BRCA1 vs BRCA2 age thresholds not differentiated.
- Cross-etiology overlap (Lynch / VHL / HLRCC patient picks up BRCA surveillance — engine isolation guard test fails).
- New regimen invented (none should be needed — surveillance is not pharmacotherapy).
- Pre-commit hooks bypassed (`--no-verify`).
- `git add -A` / `git add .` evidence.
