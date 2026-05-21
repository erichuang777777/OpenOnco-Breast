## Chunk Spec

chunks/openonco/workup-thyroid-papillary.md

## Chunk ID

workup-thyroid-papillary

## Topic Labels

evidence-draft, coverage-gap, diagnostic-workup

## Drop Estimate

~1 Drop (~80K tokens)

## Required Skill

plugins/openonco-contributor/skills/openonco-contribute/SKILL.md

## Branch Naming Convention

tasktorrent/workup-thyroid-papillary

## Sidecar Output Path

```
contributions/workup-thyroid-papillary/
```

## Task Manifest

Canonical source: `romeo111/OpenOnco` branch `master` at the latest commit when the volunteer claims this chunk.

The manifest is fixed: one Workup entity to author.

```
contributions/workup-thyroid-papillary/task_manifest.txt
```

```
WORKUP-SUSPECTED-THYROID-PAPILLARY
```

Cross-link target: `DIS-THYROID-PAPILLARY` (entity exists at `knowledge_base/hosted/content/diseases/thyroid_papillary.yaml`).

## Mission

Author the missing diagnostic Workup for `DIS-THYROID-PAPILLARY`.

Per the 2026-04-27 redflag-indication audit (`docs/reviews/redflag-indication-coverage-2026-04-27.md` §5 CRITICAL), `DIS-THYROID-PAPILLARY` is one of 5 zero-RF, zero-Indication diseases with an in-repo source available (`SRC-NCCN-THYROID-2025`). Closing the workup gap is the smallest slice — RFs and Indications are separate follow-up chunks (blocked on 2nd-source ingestion per audit §6).

The new Workup must include:
- `triage_questions` (palpable nodule, incidental US, dysphagia, hoarseness, family history).
- `mandatory_tests` (TSH, neck US with ACR-TIRADS, FNA cytology with Bethesda category).
- `risk_stratifying_tests` (molecular testing — Afirma/ThyroSeq — for indeterminate Bethesda III/IV; BRAF V600E / RET fusion / TERT promoter when relevant).
- `staging_tests` (post-resection AJCC 8th; CT neck+chest with contrast only if extra-thyroidal extension or N1b suspected).
- `cross_links_to: [DIS-THYROID-PAPILLARY]`.

**Do not change:** the disease entity itself; existing thyroid Anaplastic / MTC / Hürthle-cell content; existing sources.

## Allowed Sources

- `SRC-NCCN-THYROID-2025` (already in repo; primary).
- `SRC-ATA-THYROID-2015` (already in repo at `knowledge_base/hosted/content/sources/src_ata_thyroid_2015.yaml`; secondary if needed).
- Bethesda System for Reporting Thyroid Cytopathology (cite via NCCN cross-reference; no separate SRC).
- ACR-TIRADS (cite via NCCN cross-reference; no separate SRC).

## Disallowed Sources

OncoKB / SRC-ONCOKB, SNOMED CT, MedDRA.

## Input Context

- Source repo: `romeo111/cancer-autoresearch` branch `master`
- Disease entity: `knowledge_base/hosted/content/diseases/thyroid_papillary.yaml`
- Sibling workup template: `knowledge_base/hosted/content/workups/workup_suspected_breast.yaml`
- Schema: `knowledge_base/schemas/workup.py`
- Primary source: `knowledge_base/hosted/content/sources/src_nccn_thyroid_2025.yaml`

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch` from branch `tasktorrent/workup-thyroid-papillary`, creating:

```
knowledge_base/hosted/content/workups/workup_suspected_thyroid_papillary.yaml
```

Plus sidecar files:

```
contributions/workup-thyroid-papillary/task_manifest.txt
contributions/workup-thyroid-papillary/_contribution_meta.yaml
```

PR body must include the NCCN section locator for each `mandatory_test` and `risk_stratifying_test`.

## Acceptance Criteria (machine-checkable)

- [ ] PR branch name matches `tasktorrent/workup-thyroid-papillary`.
- [ ] One Workup YAML created at the expected path.
- [ ] References real `DIS-THYROID-PAPILLARY`.
- [ ] All `evidence_sources` reference real `SRC-*` IDs that resolve.
- [ ] Workup carries `draft: true` and `_contribution.ai_tool` + `_contribution.ai_model`.
- [ ] All test-entity references either resolve to existing `Test` entities OR are flagged `test_id_stub` for follow-up.
- [ ] KB validator green (`--strict`).
- [ ] Diff confined to the single workup YAML + sidecar folder.

## Acceptance Criteria (semantic, maintainer-checked)

- [ ] Maintainer 100% read confirms workup follows the sibling pattern + cross-link resolves.
- [ ] Clinical Co-Lead 1 of 3 sample-check (CHARTER §6.1 dev-mode exemption) confirms the diagnostic algorithm matches ATA / NCCN standard for an adult with a thyroid nodule.

## Rejection Criteria

- Treatment-recommendation language anywhere in workup (CHARTER §8.3 — workups answer "what tests", not "what treatment").
- Source citations that don't resolve.
- Disease ID reference that doesn't resolve.
- Over-staging recommendations (routine PET, routine brain MRI) not supported by NCCN-THYROID-2025 for low-risk papillary.
- Bethesda or TIRADS categories cited without anchoring to NCCN cross-reference.
- Use of OncoKB / SNOMED CT / MedDRA.
- Pre-commit hooks bypassed (`--no-verify`).
- `git add -A` / `git add .` evidence.
