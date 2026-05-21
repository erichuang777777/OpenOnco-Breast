# prevention-regimen-authoring-wave1

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

Authoring 6 named `Regimen` YAMLs for prevention interventions whose
drug entities are already in the KB. Source-driven; no new sources
required (all 7 cited sources already in repo). Light maintainer
review + Clinical Co-Lead spot-check.

## Queue
`A`

## Min Contributor Tier
`established`

## Severity
`medium`

## Topic Labels
`evidence-draft`, `coverage-gap`, `prevention`

## Mission

Author the 6 prevention `Regimen` entities explicitly named in the
v0.2-A authoring backlog
([commit `a66f47760b` follow-up](https://github.com/romeo111/cancer-autoresearch/commit/a66f47760b)):

| Regimen id | Components | Indication backlog unblocked |
|---|---|---|
| `REG-HP-BISMUTH-QUADRUPLE` | bismuth subcitrate + tetracycline + metronidazole + PPI (omeprazole) | `IND-HPYLORI-PREVENTION-ERADICATION` |
| `REG-HP-PPI-CLAR-AMOX-TRIPLE` | omeprazole + clarithromycin + amoxicillin | `IND-HPYLORI-PREVENTION-ERADICATION` (alternative track) |
| `REG-HBV-ENTECAVIR` | entecavir mono | `IND-HBV-PREVENTION-ANTIVIRAL` |
| `REG-HBV-TENOFOVIR-AF` | tenofovir alafenamide mono | `IND-HBV-PREVENTION-ANTIVIRAL` (alternative track) |
| `REG-HPV-GARDASIL-9` | nonavalent HPV vaccine (3-dose schedule) | `IND-HPV-PREVENTION-VACCINATION-SCREENING` |
| `REG-HIV-BICTARVY` | bictegravir + emtricitabine + TAF (3-drug single-tablet) | `IND-HIV-PREVENTION-ART` |

All 9 referenced drug entities already exist (per v0.2-A commit
`1eb3addfe8`). All 7 cited sources already exist (per v0.2-A commit
`a66f47760b`).

**KB coverage:** Advances v0.2-A prevention coverage from "indications
exist but `recommended_regimen: null`" to "indications point at a
real Regimen." Approximately 15 prevention indications cite one of
these 6 regimens directly or transitively.

**Out of scope:** authoring new drug entities; introducing new
sources; modifying the indications themselves (the indications
already reference these regimen IDs as placeholders); authoring
treatment regimens for non-prevention contexts.

## Drop Estimate

~2-3 Drops (~250K tokens total). 6 small Regimen YAMLs, each
~40-80 lines. Verification harness: validator + render +
indication-cross-reference test.

## Required Skill

`openonco-contributor:openonco-contribute`. Read:

- `knowledge_base/schemas/regimen.py` (canonical Regimen shape;
  `phases` field ratified 2026-05-07 per KSS §17).
- One existing prevention Regimen example:
  `knowledge_base/hosted/content/regimens/reg_tamoxifen_chemoprevention.yaml`
  (the most-recent prevention-shaped regimen in repo).
- One existing non-prevention infectious Regimen for dose-form
  reference (if any exists).

Clinical-authoring knowledge required:
- Standard adult dosing from the cited sources verbatim — do NOT
  invent dose schedules from training-data priors. Drafts that
  paraphrase dosing without a source-anchored line will be rejected.
- Recognize FDA package-insert vs guideline-recommended dosing when
  they diverge — capture both honestly in `notes:` if so.

## Allowed Sources

All in repo:

- `SRC-AASLD-HBV-2024` (entecavir, tenofovir AF dosing).
- `SRC-AASLD-IDSA-HCV-2023` (general antiviral framing).
- `SRC-AGA-H-PYLORI-2024` (H. pylori triple + quadruple regimens).
- `SRC-ACG-H-PYLORI-2024` (alternative US guideline).
- `SRC-IARC-MONOGRAPH-100B-2012` (HPV vaccination rationale).
- `SRC-NIH-AIDS` / `SRC-DHHS-HIV-2024` (HIV ART selection — confirm
  exact src-id when chunk-task issue opens).
- DailyMed / openFDA per-drug package inserts (already-allowed
  reference per source-allowlist; for verbatim dose extraction).

**Banned per OpenOnco pilot:** OncoKB, SNOMED CT, MedDRA. Not
relevant here.

## Manifest

| Field | Value |
|---|---|
| `regimen_ids` | 6 listed above |
| `regimen_target_paths` | `knowledge_base/hosted/content/regimens/reg_hp_bismuth_quadruple.yaml`, `reg_hp_ppi_clar_amox_triple.yaml`, `reg_hbv_entecavir.yaml`, `reg_hbv_tenofovir_af.yaml`, `reg_hpv_gardasil_9.yaml`, `reg_hiv_bictarvy.yaml` |
| `referenced_drug_ids` | `DRUG-BISMUTH-SUBCITRATE`, `DRUG-TETRACYCLINE`, `DRUG-METRONIDAZOLE`, `DRUG-OMEPRAZOLE`, `DRUG-CLARITHROMYCIN`, `DRUG-AMOXICILLIN`, `DRUG-ENTECAVIR`, `DRUG-TENOFOVIR-AF`, `DRUG-GARDASIL-9`, `DRUG-BICTEGRAVIR-EMTRICITABINE-TAF` (exact ids confirmed when issue opens) |
| `validator_command` | `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| `cross_ref_command` | `python -c "from knowledge_base.validation.loader import load_all; e = load_all('knowledge_base/hosted/content'); print([i.id for i in e if i.kind == 'Indication' and i.recommended_regimen in {'REG-HP-BISMUTH-QUADRUPLE', ...}])"` (full one-liner in issue) |

Manifest is concrete: all 6 regimen IDs are already referenced
from existing prevention indications as placeholders. All 9
referenced drug entities + all 7 cited sources are already in the
KB.

## Computation

For each of the 6 regimens:

1. **Read** the existing prevention Indication that references the
   placeholder `recommended_regimen` (e.g.
   `ind_hpylori_prevention_eradication.yaml` for the two H. pylori
   regimens). The indication's `applicable_to`,
   `recommended_for_intent`, and prose context tell you what the
   regimen needs to look like.
2. **Read** the cited source verbatim for dosing. For
   `REG-HP-BISMUTH-QUADRUPLE`, that's `SRC-AGA-H-PYLORI-2024`
   Table X (locator in the source entity). Copy dosing strings
   verbatim into `regimen.components[].typical_dose` — do not
   paraphrase.
3. **Author** the Regimen YAML using the canonical shape:
   - `id:`, `kind: Regimen`, `name:`, `name_uk:`
   - `intent: prevention` (per KSS §20)
   - `components: [{drug_id: DRUG-*, typical_dose: "...", route: ..., schedule: "..."}]`
   - `cycle_length:` if applicable (typically null for prevention)
   - `phases:` per KSS §17 (typically `[induction]` for finite
     courses, `[maintenance]` for long-term suppression)
   - `evidence_sources: [{source_id: SRC-*, snippet: "..."}]`
   - `notes:` for FDA-vs-guideline divergence honest capture
   - `_contribution: {ai_tool: ..., ai_model: ..., draft: true,
     reviewer_signoffs: 0}`
4. **Validate** `py -3.12 -m knowledge_base.validation.loader
   knowledge_base/hosted/content --strict` — green.
5. **Cross-reference** that the existing prevention indication
   resolves its `recommended_regimen` to the newly-authored
   regimen (run `cross_ref_command`).
6. **Render** one example prevention Plan that pulls the regimen,
   confirm the regimen surfaces in the HCP-mode + patient-mode
   render via `pytest tests/test_prevention_render.py`.

If a drug entity is missing or named differently than the
indication's placeholder, **stop and surface to maintainer** —
naming alignment is a separate scoped change.

## Where computation happens

Contributor's machine. Python 3.12; web access for source
locator URLs; PR against `master`.

## Re-verification

### Pre-acceptance gates (auto-reject)

- KB validator green (`--strict`).
- All 6 regimen YAMLs reference real `DRUG-*` IDs that resolve.
- All `evidence_sources` reference real `SRC-*` IDs that resolve.
- All 6 regimens carry `intent: prevention`.
- All 6 regimens carry `draft: true` and `_contribution.ai_tool` +
  `ai_model`.
- `cross_ref_command` confirms all 6 regimens are reachable from
  ≥1 prevention Indication each.
- `pytest tests/test_prevention_render.py
  tests/test_prevention_engine.py` green.

### Computational re-verify

None (judgment-driven authoring; deterministic checks above suffice
for pre-acceptance).

### Sample human re-verify

- **Maintainer (1 person, 100% read):** verify all 6 regimens cite
  source-verbatim dosing strings, not paraphrased. Spot-check 2 of
  6 against the actual source PDF / web page.
- **Clinical Co-Lead (1 of 3, 100% read):** verify dose schedules
  match standard-of-care for the intended population
  (immunocompetent adult; resource-rich + resource-limited
  variants noted where relevant). CHARTER §6.1 dev-mode
  exemption applies — single Co-Lead sample-check sufficient
  during v0.1.

### Trust threshold

- 1 of 1 maintainer review.
- 1 of 3 Clinical Co-Lead sample-check.
- Drafts ship `draft: true`; flip to non-draft + add second Co-Lead
  signoff later when v0.1 dev-mode exemption is lifted.

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch`,
branch `feat/prevention-regimens-wave1-2026-05-20-HHMM`, creating:

```
knowledge_base/hosted/content/regimens/reg_hp_bismuth_quadruple.yaml
knowledge_base/hosted/content/regimens/reg_hp_ppi_clar_amox_triple.yaml
knowledge_base/hosted/content/regimens/reg_hbv_entecavir.yaml
knowledge_base/hosted/content/regimens/reg_hbv_tenofovir_af.yaml
knowledge_base/hosted/content/regimens/reg_hpv_gardasil_9.yaml
knowledge_base/hosted/content/regimens/reg_hiv_bictarvy.yaml
```

Plus a contribution-meta sidecar under
`contributions/prevention-regimen-authoring-wave1/_contribution_meta.yaml`.

PR description must list each regimen with its cited source +
verbatim dose-snippet.

## Acceptance Criteria

- All pre-acceptance gates pass.
- 100% maintainer read; 2-of-6 source-PDF spot-check confirmed.
- 1 of 3 Clinical Co-Lead sample-check signed.
- All 6 regimens carry `intent: prevention` and `draft: true`.

## Rejection Criteria

- Dosing strings paraphrased rather than source-verbatim.
- Drug entity references that don't resolve.
- Source citations that don't resolve.
- `intent:` field missing or set to `treatment`.
- Treatment-recommendation language in `notes:` or `rationale:`
  (CHARTER §8.3).
- Invented dose schedule not attested in cited source.

## Claim Method

`trusted-agent-wip-branch-first`. Volunteer opens `[Chunk]
prevention-regimen-authoring-wave1` issue against
`romeo111/task_torrent`; pushes WIP branch within 48 h; opens PR
within 7 working days (longer than algo-wiring chunks because of
the source-extraction step + Co-Lead review).

## Reviewer

- Maintainer: 1.
- Clinical Co-Lead signoff: 1 of 3 (sample-check; not 2-of-3
  publication gate) per CHARTER §6.1 dev-mode exemption.

## Notes

Wave 1 of N. Wave 2 candidates already identified in v0.2-A
backlog: `REG-PREEMPTIVE-RITUXIMAB-PTLD-PROPHYLAXIS`,
`REG-VALACYCLOVIR-EBV-SUPPRESSION-PTLD`, additional HIV-ART
combinations beyond Bictarvy. Wave 3 candidates from v0.2-B
hereditary: `REG-ASPIRIN-LYNCH-CAPP2`,
`REG-EXEMESTANE-MAP3-BREAST-RISK-REDUCTION` (exemestane already in
repo for chemoprevention — confirm whether existing entity covers
this indication or new regimen needed).

This is the **first prevention chunk on the shelf** — establishes
the pattern for v0.2-B confirmed-carrier surveillance chunks (see
sibling `hereditary-brca-carrier-surveillance` in this wave). If
the dosing-verbatim discipline holds, subsequent prevention-content
chunks can use the same shape.
