# hereditary-brca-carrier-surveillance

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

Author the post-test-positive surveillance pathway for confirmed
BRCA1/2 germline carriers — one `RedFlag` + one `Indication` +
optional `Algorithm` step extension. Closes a v0.2-B continuation
gap explicitly listed in the OpenOnco roadmap.

## Queue
`A`

## Min Contributor Tier
`established`

## Severity
`medium`

## Topic Labels
`evidence-draft`, `coverage-gap`, `prevention`, `hereditary`

## Mission

The v0.2-B hereditary pilot (commit `f252a24e5d`) shipped the
pedigree-suspicion RF + the genetic-counseling / decline-testing
tracks for BRCA / HBOC, but stopped short of the post-test-positive
pathway. Per the roadmap entry for v0.2-B:

> Pending v0.2-B continuation: confirmed-carrier surveillance
> pathways (RF-*-CONFIRMED-CARRIER + IND-*-CARRIER-SURVEILLANCE
> post-test-positive).

This chunk closes the pathway for BRCA1/2:

| Entity | Purpose |
|---|---|
| `RF-BRCA-CONFIRMED-CARRIER` | Fires on a positive germline BRCA1/2 result (existing `BIO-BRCA1-GERMLINE` or `BIO-BRCA2-GERMLINE` value: `positive`). |
| `IND-BRCA-CARRIER-ENHANCED-SURVEILLANCE` | Standard enhanced surveillance track — annual breast MRI + mammography starting age 25-30, semi-annual breast clinical exam, TVUS + CA-125 every 6 months until RRSO, RRSO discussion age 35-40 (BRCA1) / 40-45 (BRCA2). |
| `IND-BRCA-CARRIER-RISK-REDUCTION` | Alternative track — risk-reducing mastectomy + RRSO discussion per shared-decision-making framework. Two-track pattern per CHARTER §15.2 C4. |

The existing `RF-BRCA-HBOC-FAMILY-HISTORY-SUSPICION` continues to
fire pre-testing; the new `RF-BRCA-CONFIRMED-CARRIER` takes over
post-result. Both can coexist (graceful handoff).

**KB coverage:** Closes 1 of 5 v0.2-B confirmed-carrier pathway
gaps. Establishes template for sibling chunks: Lynch, FAP, VHL,
HLRCC.

**Out of scope:** authoring the risk-reducing surgery details
themselves (Surgery entity ratified in KSS §17 but contraceptive
+ pregnancy + bone-density management for post-RRSO patients is a
separate clinical scope); modifying the existing pre-testing RF
+ counseling-track indications; cascade testing for first-degree
relatives (covered by existing `algo_cascade_family_testing.yaml`);
clinical management of confirmed cancer (treatment-side, not
prevention-side).

## Drop Estimate

~1.5 Drops (~150K tokens). 1 RF + 2 Indications + (optional)
algorithm step extension + tests.

## Required Skill

`openonco-contributor:openonco-contribute` +
`openonco-contributor:biomarker-sidecar-draft` (the latter for
`RF-*-CONFIRMED-CARRIER` since it's keyed on a Biomarker positive
result; the skill enforces neutral-evidence wording and the
banned-source policy).

Read:

- `knowledge_base/schemas/redflag.py` for the RF shape — note the
  `risk_category: hereditary` enum value (per KSS §20.4).
- The sibling pre-testing RF
  `knowledge_base/hosted/content/redflags/rf_brca_hboc_family_history_suspicion.yaml`
  for the structural template.
- The two existing BRCA / HBOC pre-testing indications under
  `knowledge_base/hosted/content/indications/ind_brca_hboc_suspicion_prevention_*.yaml`
  for the prevention-Indication shape (`intent: prevention`,
  `recommended_for_intent: prevention`).
- The Lynch starter under
  `knowledge_base/hosted/content/redflags/` for the cross-etiology
  isolation guard pattern (added in commit `8e1b05e43f`).

Clinical-authoring knowledge required:
- NCCN Genetic / Familial High-Risk Breast/Ovarian v3.2025
  surveillance recommendations for BRCA1 vs BRCA2 carriers (the
  age thresholds differ; capture honestly).
- ESMO + NICE positions on RRSO timing (some divergence;
  capture in `notes:` without picking a winner per
  CLINICAL_CONTENT_STANDARDS §1.2).

## Allowed Sources

- `SRC-NCCN-GENETIC-FAMILIAL-BREAST-OVARIAN-2025` (already in
  repo per commit `a66f47760b`). **Note:** `legal_review.status:
  escalated` per scope-proposal Q7. If the legal review resolves
  against this source by chunk-claim-time, fall back to the ASCO
  / ACMG joint guideline.
- `SRC-ASCO-ACMG-LYNCH-2014` (precedent for cascade-testing
  language; useful for cross-etiology comparison even though it's
  Lynch-specific).
- USPSTF Grade B recommendations on BRCA risk assessment and
  testing (cite via primary `SRC-USPSTF-BRCA-202X` if it exists in
  repo; otherwise flag for `source-stub-ingest-batch` follow-up).
- ESMO + NICE — cite via repo `SRC-*` if present; otherwise flag.

**Banned per OpenOnco pilot:** OncoKB, SNOMED CT, MedDRA. Not
relevant to hereditary surveillance authoring.

## Manifest

| Field | Value |
|---|---|
| `entities_authored` | 1 RF + 2 Indications |
| `rf_id` | `RF-BRCA-CONFIRMED-CARRIER` |
| `rf_target_path` | `knowledge_base/hosted/content/redflags/rf_brca_confirmed_carrier.yaml` |
| `indication_ids` | `IND-BRCA-CARRIER-ENHANCED-SURVEILLANCE`, `IND-BRCA-CARRIER-RISK-REDUCTION` |
| `indication_target_paths` | `knowledge_base/hosted/content/indications/ind_brca_carrier_enhanced_surveillance.yaml`, `ind_brca_carrier_risk_reduction.yaml` |
| `disease_ids_linked` | `DIS-BREAST`, `DIS-OVARIAN`, `DIS-PROSTATE`, `DIS-PDAC`, `DIS-MELANOMA` (per existing BRCA BMA cells) |
| `biomarker_ids_referenced` | `BIO-BRCA1`, `BIO-BRCA2` (germline positive triggers the RF) |
| `existing_pre_testing_rf` | `RF-BRCA-HBOC-FAMILY-HISTORY-SUSPICION` (continues to fire pre-testing; new RF takes over post-result) |
| `cross_etiology_isolation_check` | Lynch ↔ BRCA via DIS-BREAST + DIS-OVARIAN overlap — must use `triggered_by_redflags` engine guard (added 2026-05-18) |
| `validator_command` | `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| `golden_test_command` | `pytest tests/test_prevention_engine.py -k brca` |

Existing entities referenced are all in repo. The cross-etiology
isolation guard is a real engine feature already shipped.

## Computation

1. **Read** the existing pre-testing pair:
   - `rf_brca_hboc_family_history_suspicion.yaml`
   - `ind_brca_hboc_suspicion_prevention_genetic_counseling.yaml`
   - `ind_brca_hboc_suspicion_prevention_enhanced_surveillance.yaml`
2. **Read** the Lynch sibling for cross-etiology isolation pattern
   (commit `8e1b05e43f`).
3. **Author** the new `RF-BRCA-CONFIRMED-CARRIER`:
   - `risk_category: hereditary` (per KSS §20.4).
   - `trigger:` block keyed on
     `BIO-BRCA1: positive` OR `BIO-BRCA2: positive` (germline
     subtype only — somatic is treatment-side, not prevention).
   - `relevant_diseases: [DIS-BREAST, DIS-OVARIAN, DIS-PROSTATE,
     DIS-PDAC, DIS-MELANOMA]` (per existing BRCA BMA cells).
   - `clinical_direction: investigate` (alternative-track
     trigger; not a contra-indication).
   - `shifts_algorithm: []` (RF fires standalone; new indications
     pick it up via `triggered_by_redflags`).
   - `evidence_sources: [SRC-NCCN-GENETIC-FAMILIAL-BREAST-OVARIAN-2025,
     SRC-USPSTF-BRCA-202X (or stub)]`.
   - `draft: true`, `_contribution: {...}`.
4. **Author** `IND-BRCA-CARRIER-ENHANCED-SURVEILLANCE`:
   - `intent: prevention`.
   - `triggered_by_redflags: [RF-BRCA-CONFIRMED-CARRIER]` —
     the engine cross-etiology isolation guard ensures Lynch / FAP
     / VHL / HLRCC carriers don't accidentally pick this up.
   - `recommended_for_intent: prevention`.
   - `recommended_regimen: null` (no Regimen entity needed —
     surveillance is imaging + clinical-exam, not pharmacotherapy).
   - Standard enhanced surveillance per NCCN-GENETIC-FAMILIAL —
     verbatim source-anchored bullet points in `rationale_uk`.
   - Differentiate BRCA1 vs BRCA2 age thresholds honestly.
5. **Author** `IND-BRCA-CARRIER-RISK-REDUCTION`:
   - `intent: prevention`.
   - Same `triggered_by_redflags`.
   - Alternative track per §15.2 C4 — risk-reducing mastectomy +
     RRSO via shared-decision-making framework. Verbatim source
     anchoring; do NOT make a recommendation between tracks
     (CHARTER §8.3).
6. **Validate** `--strict` → green.
7. **Run** `pytest tests/test_prevention_engine.py -k brca` →
   confirm a synthetic patient with `BIO-BRCA1: positive`
   produces a PreventionPlan with both tracks.

## Where computation happens

Contributor's machine. Python 3.12; web access for NCCN-Genetic /
USPSTF source confirmation; PR against `master`.

## Re-verification

### Pre-acceptance gates (auto-reject)

- KB validator green (`--strict`).
- 3 new entities (1 RF + 2 Indications) all reference real
  `BIO-*`, `DIS-*`, `SRC-*` IDs that resolve.
- All 3 entities carry `draft: true` and `_contribution.ai_tool`
  + `ai_model`.
- RF carries `risk_category: hereditary` (per KSS §20.4).
- Both Indications carry `intent: prevention` (per KSS §20.4) and
  `triggered_by_redflags: [RF-BRCA-CONFIRMED-CARRIER]`.
- Engine cross-etiology isolation guard test passes:
  `pytest tests/test_prevention_engine.py::test_brca_carrier_does_not_trigger_lynch_surveillance`
  (new test; volunteer authors it alongside the entities).
- ≥2 source citations on the RF (publication gate).

### Computational re-verify

`pytest tests/test_prevention_engine.py -k brca` green; PreventionPlan
synthesizer produces 2-track output for BRCA1+ synthetic patient.

### Sample human re-verify

- **Maintainer (1 person, 100% read):** verify cross-etiology
  isolation pattern matches the Lynch sibling; verify source
  citations resolve; verify no treatment recommendation language.
- **Clinical Co-Lead (1 of 3, 100% read):** verify surveillance
  schedule matches NCCN-GENETIC-FAMILIAL standard for BRCA1 vs
  BRCA2 (the age thresholds differ); verify the risk-reduction
  track is presented as a discussion not a recommendation.
  CHARTER §6.1 dev-mode exemption applies.

### Trust threshold

- 1 of 1 maintainer review.
- 1 of 3 Clinical Co-Lead sample-check.
- Drafts ship `draft: true`; flip to non-draft when v0.1 dev-mode
  exemption is lifted.

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch`,
branch `feat/brca-carrier-surveillance-2026-05-20-HHMM`, creating:

```
knowledge_base/hosted/content/redflags/rf_brca_confirmed_carrier.yaml
knowledge_base/hosted/content/indications/ind_brca_carrier_enhanced_surveillance.yaml
knowledge_base/hosted/content/indications/ind_brca_carrier_risk_reduction.yaml
tests/test_prevention_engine.py    # one new test (cross-etiology isolation)
```

Plus a contribution-meta sidecar under
`contributions/hereditary-brca-carrier-surveillance/_contribution_meta.yaml`.

PR description must include:

- Section locator from `SRC-NCCN-GENETIC-FAMILIAL-BREAST-OVARIAN-2025`
  for the surveillance schedule, BRCA1 vs BRCA2 age thresholds, and
  RRSO timing.
- Cross-etiology isolation test output (Lynch + VHL + HLRCC patient
  profiles confirm they do NOT trigger BRCA carrier surveillance).
- Diff size: ≤ 250 LOC (3 entity YAMLs + 1 test).

## Acceptance Criteria

- All pre-acceptance gates pass.
- 100% maintainer + 1 of 3 Co-Lead sample-check signed.
- All 3 entities carry `draft: true`.
- Cross-etiology isolation test passes.

## Rejection Criteria

- Treatment recommendation language in `rationale` / `notes`
  (CHARTER §8.3 — surveillance/discussion only, no "you should
  have RRSO at age 38").
- Single-track output (CHARTER §15.2 C4 requires ≥2 tracks).
- Source citations that don't resolve.
- Use of OncoKB, SNOMED CT, or MedDRA in any citation.
- BRCA1 vs BRCA2 age thresholds not differentiated.
- Cross-etiology overlap (e.g. Lynch patient picks up BRCA
  surveillance) — engine isolation guard test fails.
- New regimen invented (none should be needed — surveillance is
  not pharmacotherapy).

## Claim Method

`trusted-agent-wip-branch-first`. Volunteer opens `[Chunk]
hereditary-brca-carrier-surveillance` issue against
`romeo111/task_torrent`; pushes WIP branch within 48 h; opens PR
within 7 working days.

## Reviewer

- Maintainer: 1.
- Clinical Co-Lead signoff: 1 of 3 sample-check (CHARTER §6.1
  dev-mode exemption).

## Notes

First of **5 sibling chunks** for confirmed-carrier surveillance.
Successors:

- `hereditary-lynch-carrier-surveillance` (NCCN-Genetic-Familial-CRC;
  ASCO-ACMG-Lynch-2014 second source).
- `hereditary-fap-carrier-surveillance` (NCCN-Genetic-Familial-CRC;
  Bisgaard-FAP-2006 second source).
- `hereditary-vhl-carrier-surveillance` (likely needs
  `source-stub-ingest-batch` to bring in an IRC-VHL or NCI-VHL
  source).
- `hereditary-hlrcc-carrier-surveillance` (similar source-ingest
  dependency).

The `SRC-NCCN-GENETIC-FAMILIAL-*` sources carry
`legal_review.status: escalated` per scope-proposal Q7. If the
legal review resolves *against* hosting NCCN-Genetic-Familial
content, this chunk falls back to USPSTF + ASCO-ACMG primary
attribution. The chunk-task issue, when opened, must capture the
current legal-review status as of the claim date so the volunteer
knows which source set to anchor against.

After this chunk + the prevention-regimen-authoring-wave1 chunk
both land, v0.2-A and v0.2-B move from "indications exist with
placeholders" to "complete prevention pathways with regimens or
surveillance schedules wired in." That's the visible KB delta the
user can point at when describing v0.2 to a clinical reviewer.
