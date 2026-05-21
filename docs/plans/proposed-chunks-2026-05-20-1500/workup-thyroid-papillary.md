# workup-thyroid-papillary

## Status
`queued`

## Economic Profile
```yaml
compute_profile: low
verification_method: full-expert
break_even_test: PASS
output_type: entity-yaml-new
backfilled_retroactively: false
```

Author one `Workup` YAML for `DIS-THYROID-PAPILLARY` against
`SRC-NCCN-THYROID-2025`. Smallest possible scope for a volunteer's
first KB-authoring chunk — single entity, single source, no
algorithm wiring.

## Queue
`A`

## Min Contributor Tier
`new`

## Severity
`low`

## Topic Labels
`evidence-draft`, `coverage-gap`, `diagnostic-workup`

## Mission

Author the missing `Workup` entity for `DIS-THYROID-PAPILLARY`.

Per the 2026-04-27 redflag-indication audit
([docs/reviews/redflag-indication-coverage-2026-04-27.md §5
CRITICAL](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/reviews/redflag-indication-coverage-2026-04-27.md)),
`DIS-THYROID-PAPILLARY` is one of 5 zero-RF, zero-Indication
diseases with an in-repo source available
(`SRC-NCCN-THYROID-2025`). The disease entity exists at
[knowledge_base/hosted/content/diseases/thyroid_papillary.yaml](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/hosted/content/diseases/thyroid_papillary.yaml)
but has no diagnostic workup, no RedFlag coverage, and no
treatment Indications. Closing the workup gap is the smallest
slice — RFs + Indications are follow-up chunks.

The new Workup must include:

- `triage_questions` (clinical features that direct biopsy vs
  surveillance).
- `mandatory_tests` (FNA cytology with Bethesda category, neck US
  with ACR-TIRADS, TSH).
- `risk_stratifying_tests` (molecular testing for indeterminate
  Bethesda III/IV nodules; ATA risk stratification inputs).
- `staging_tests` (post-resection: AJCC 8th, cross-sectional imaging
  if clinically warranted).
- `cross_links_to: [DIS-THYROID-PAPILLARY]`.

**KB coverage:** Closes 1 of 5 CRITICAL zero-workup gaps. Establishes
template for sibling chunks `workup-thyroid-anaplastic`,
`workup-mtc`, `workup-mastocytosis`, `workup-glioma-low-grade`.

**Out of scope:** authoring `RedFlag` or `Indication` entities for
DIS-THYROID-PAPILLARY (separate follow-up chunks); ingesting a
2nd source for the 2-source RF gate (separate
`source-stub-ingest-batch` work); reorganizing existing thyroid
disease entities; touching anaplastic / medullary / Hürthle-cell
content.

## Drop Estimate

~1 Drop (~80K tokens). One Workup YAML ~60-100 lines, plus tests
that confirm cross-reference resolution.

## Required Skill

`openonco-contributor:openonco-contribute`. Read:

- `knowledge_base/schemas/workup.py` for the Workup shape.
- A canonical Workup example:
  `knowledge_base/hosted/content/workups/workup_suspected_breast.yaml`
  (similar shape: solid-tumor, biopsy-driven, AJCC-staged).
- The disease entity
  `knowledge_base/hosted/content/diseases/thyroid_papillary.yaml`
  for what archetype the disease declares + what biomarkers it
  references (BIO-BRAF-V600E, BIO-RET-FUSION, BIO-TERT-PROMOTER).

Clinical-authoring knowledge required:
- Familiarity with the ATA / NCCN thyroid nodule workup standard
  (FNA + Bethesda + ACR-TIRADS + molecular testing for
  indeterminate cytology).
- Recognize that this is a low-aggression histology — the workup
  should not over-stage or trigger systemic imaging routinely.

## Allowed Sources

- `SRC-NCCN-THYROID-2025` (already in repo; primary).
- `SRC-ATA-THYROID-2015` (already in repo per
  `knowledge_base/hosted/content/sources/src_ata_thyroid_2015.yaml`;
  secondary if needed).
- Bethesda System for Reporting Thyroid Cytopathology (cited via
  NCCN cross-reference; no separate SRC needed if the workup quotes
  Bethesda categories without claiming the Bethesda system as a
  primary source itself).
- ACR-TIRADS (similar — cited via NCCN, no separate SRC needed).

**Banned per OpenOnco pilot:** OncoKB, SNOMED CT, MedDRA. Not
relevant here.

## Manifest

| Field | Value |
|---|---|
| `workup_id` | `WORKUP-SUSPECTED-THYROID-PAPILLARY` |
| `workup_target_path` | `knowledge_base/hosted/content/workups/workup_suspected_thyroid_papillary.yaml` |
| `disease_id_linked` | `DIS-THYROID-PAPILLARY` |
| `validator_command` | `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| `golden_test_command` | `pytest tests/test_diagnostic_engine.py -k thyroid` (skip if no thyroid fixture yet — pre-condition for follow-up RF + IND chunks to add fixtures) |

Manifest is concrete — disease entity exists, primary + secondary
sources exist, schema is documented.

## Computation

1. **Read** the disease entity
   [knowledge_base/hosted/content/diseases/thyroid_papillary.yaml](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/hosted/content/diseases/thyroid_papillary.yaml)
   for what biomarkers are declared (so the workup's
   `risk_stratifying_tests` can target them).
2. **Read** the primary source
   `knowledge_base/hosted/content/sources/src_nccn_thyroid_2025.yaml`
   for the section locator that documents the diagnostic algorithm
   (typically NCCN-THY-1 + THY-2 pages).
3. **Read** a sibling workup
   (`workup_suspected_breast.yaml`) as the structural template.
4. **Author** the Workup YAML:
   - `id: WORKUP-SUSPECTED-THYROID-PAPILLARY`, `kind: Workup`,
     `name`, `name_uk`.
   - `cross_links_to: [DIS-THYROID-PAPILLARY]`.
   - `triage_questions: [...]` — palpable nodule? incidental US?
     dysphagia? hoarseness? family hx?
   - `mandatory_tests: [...]` — TSH, neck US ACR-TIRADS, FNA
     cytology Bethesda.
   - `risk_stratifying_tests: [...]` — molecular testing
     (Afirma/ThyroSeq) for indeterminate Bethesda III/IV;
     BRAF V600E / RET fusion / TERT promoter when relevant.
   - `staging_tests: [...]` — post-resection AJCC 8th; CT
     neck+chest with contrast if extra-thyroidal extension /
     N1b suspected.
   - `evidence_sources: [{source_id: SRC-NCCN-THYROID-2025,
     snippet: "...", section_locator: "..."}]`.
   - `_contribution: {ai_tool, ai_model, draft: true,
     reviewer_signoffs: 0}`.
5. **Validate** `--strict` → green.
6. **Cross-check** that
   `knowledge_base/hosted/content/diseases/thyroid_papillary.yaml`
   either references the new workup ID OR can be linked by a
   follow-up disease-entity edit (separate chunk; not in scope
   here).

## Where computation happens

Contributor's machine. Python 3.12; web access for NCCN/ATA source
locator confirmation (NCCN guidelines require free registration);
PR against `master`.

## Re-verification

### Pre-acceptance gates (auto-reject)

- KB validator green (`--strict`).
- Workup YAML references real `DIS-THYROID-PAPILLARY`.
- All `evidence_sources` reference real `SRC-*` IDs.
- Workup YAML carries `draft: true` and `_contribution.ai_tool` +
  `ai_model`.
- All test-entity references (e.g. `TEST-TSH`,
  `TEST-NECK-US-TIRADS`, `TEST-FNA-BETHESDA`) either resolve to
  existing `Test` entities OR are flagged as `test_id_stub` for
  follow-up authoring.
- Diff confined to the single new workup YAML file +
  contribution-meta sidecar.

### Computational re-verify

None (judgment-driven authoring).

### Sample human re-verify

- **Maintainer (1 person, 100% read):** verify workup follows the
  established sibling pattern; cross-link resolves.
- **Clinical Co-Lead (1 of 3, 100% read):** verify diagnostic
  algorithm matches ATA / NCCN standard for the immunocompetent
  adult with a thyroid nodule. CHARTER §6.1 dev-mode exemption
  applies.

### Trust threshold

- 1 of 1 maintainer review.
- 1 of 3 Clinical Co-Lead sample-check.
- Drafts ship `draft: true`.

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch`,
branch `feat/workup-thyroid-papillary-2026-05-20-HHMM`, creating:

```
knowledge_base/hosted/content/workups/workup_suspected_thyroid_papillary.yaml
```

Plus a contribution-meta sidecar under
`contributions/workup-thyroid-papillary/_contribution_meta.yaml`.

PR description must include:

- Section locator from `SRC-NCCN-THYROID-2025` for each
  `mandatory_test` and `risk_stratifying_test`.
- Confirmation that the disease entity already exists + is
  cross-linked.
- Diff-size: ≤ 100 LOC.

## Acceptance Criteria

- All pre-acceptance gates pass.
- 100% maintainer + 1 of 3 Co-Lead sample-check signed.
- Workup carries `draft: true`.

## Rejection Criteria

- Treatment-recommendation language anywhere in workup (CHARTER
  §8.3 — workups answer "what tests" not "what treatment").
- Source citations that don't resolve.
- Disease ID reference that doesn't resolve.
- Over-staging recommendations (routine PET, routine MRI brain)
  not supported by NCCN-THYROID-2025 for low-risk papillary.
- Bethesda or TIRADS categories cited without anchoring to NCCN
  cross-reference.

## Claim Method

`trusted-agent-wip-branch-first`. Volunteer opens `[Chunk]
workup-thyroid-papillary` issue against `romeo111/task_torrent`;
pushes WIP branch within 48 h; opens PR within 5 working days.

## Reviewer

- Maintainer: 1.
- Clinical Co-Lead signoff: 1 of 3 sample-check (CHARTER §6.1
  dev-mode exemption).

## Notes

First of **5 sibling chunks** for source-available zero-RF
diseases. After this validates the workup-authoring pattern, the
maintainer can spin up:

- `workup-thyroid-anaplastic` (NCCN-THYROID; airway-emergency
  bias — workup must flag urgency).
- `workup-mtc` (NCCN-THYROID + calcitonin marker; cross-link to
  `DIS-MTC` MEN2 family).
- `workup-mastocytosis` (NCCN-SM-2025; tryptase + KIT D816V
  testing).
- `workup-glioma-low-grade` (NCCN-CNS-2025; IDH + 1p19q + MGMT
  molecular workup).

The follow-up RF chunks for these diseases are BLOCKED on
2nd-source ingestion per the 2026-04-27 audit. The workup itself
has no 2-source gate, so it can land standalone.

This chunk does NOT close the 5-type matrix gap for
DIS-THYROID-PAPILLARY (still 5/5 missing) — that's a separate
follow-up requiring `source-stub-ingest-batch` to bring in
`SRC-ATA-MTC-2015` and any other 2nd source per audit §6.
