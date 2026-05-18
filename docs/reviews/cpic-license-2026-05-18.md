# CPIC license review — 2026-05-18

Per `specs/SOURCE_INGESTION_SPEC.md` §8 and §20. Classifies the Clinical
Pharmacogenetics Implementation Consortium (CPIC) corpus for OpenOnco
reuse.

## TL;DR

- **Guideline text license:** CC BY 4.0 (SPDX `CC-BY-4.0`).
- **Underlying data tables license:** CC0 1.0 (allele functionality,
  diplotype→phenotype, drug recommendation mappings).
- **Hosting mode:** `referenced`.
- **Four constraints clear:** commercial ✓, redistribution ✓, modification ✓.
- **Share-alike:** NOT required (CC BY 4.0; CC0 has no obligations at all).
- **Attribution:** **required for guideline text** (CC BY 4.0 obligation);
  not required for the CC0 data tables but courteous.
- **`legal_review.status: reviewed`.**

## What CPIC is

The Clinical Pharmacogenetics Implementation Consortium (CPIC) is an
international consortium of pharmacogenetics experts that publishes
peer-reviewed clinical guidelines for translating genotype information
into actionable prescribing decisions. CPIC is hosted at the University
of Pennsylvania, funded by the NIH (R24GM115264) and collaborates with
PharmGKB.

Each guideline:

- Names a specific gene-drug pair (e.g. DPYD-fluoropyrimidine,
  TPMT-thiopurines, CYP2D6-tamoxifen).
- Provides allele-function tables (haplotype → metabolic phenotype).
- Provides dosing recommendations stratified by phenotype.
- Carries a CPIC level (A, B, C, D) reflecting strength of evidence.
- Is updated when new evidence emerges (typical cadence: ~quarterly
  for new guidelines / updates across the catalog).

Public-facing URLs:
- Guidelines index: <https://cpicpgx.org/guidelines/>
- API: <https://api.cpicpgx.org/v1/> (PostgREST)
- Data schema: <https://github.com/cpicpgx/cpic-data>

## Why we want it

Pharmacogenomic dosing is currently invisible in the OpenOnco engine. A
patient with a DPYD poor-metaboliser genotype routed to FOLFOX or
capecitabine should see a *hard* RedFlag: full-dose fluoropyrimidine in
DPD-deficient patients causes life-threatening toxicity (G3-G5
mucositis, neutropenia, diarrhea). The CPIC DPYD-fluoropyrimidine
guideline (Amstutz et al, CPT 2017, updated 2020) gives the exact
dose-reduction table by metaboliser phenotype.

Same shape for:
- **TPMT and NUDT15 → thiopurines** (6-MP, azathioprine, thioguanine
  in pediatric ALL maintenance — Relling et al, CPT 2019).
- **CYP2D6 → tamoxifen** (endocrine therapy in HR+ breast cancer —
  Goetz et al, CPT 2018).
- **UGT1A1 → irinotecan** (CRC FOLFIRI / FOLFOXIRI dose adjustment —
  not yet a full CPIC guideline but in the pipeline).

These are all directly applicable to existing OpenOnco regimens (FOLFOX,
FOLFIRI, FOLFOXIRI, capecitabine-based, tamoxifen adjuvant, 6-MP
maintenance). Adding CPIC unlocks a whole new RedFlag layer without
new clinical content authoring beyond the structured mapping.

## License classification

### Guideline text — CC BY 4.0

The CPIC guideline manuscripts are published in *Clinical Pharmacology
& Therapeutics* and on cpicpgx.org under CC BY 4.0 — the most
permissive of the major CC licenses requiring attribution. The
[CPIC website footer](https://cpicpgx.org/) and
[GitHub repository](https://github.com/cpicpgx/cpic-data#license)
both confirm CC BY 4.0 for guideline text.

### Data tables — CC0 1.0

The structured CPIC database (allele definitions, diplotype-to-phenotype
maps, dosing tables) is released under CC0 — i.e. dedicated to the
public domain worldwide. Per the
[cpic-data repository](https://github.com/cpicpgx/cpic-data) license
file, the database is "released into the public domain under the CC0
license."

### Four-constraint check (per `SOURCE_INGESTION_SPEC §8`)

| Constraint | Guideline text (CC BY 4.0) | Data tables (CC0) |
| --- | --- | --- |
| Commercial use allowed? | **Yes** | **Yes** |
| Redistribution allowed? | **Yes** | **Yes** |
| Modifications allowed? | **Yes** | **Yes** |
| ShareAlike required? | **No** | **No** |
| Attribution required? | **Yes** | No (but courteous) |

Compatible with `CHARTER §2` (free public resource, non-commercial
posture) — CC BY 4.0 is freely compatible with non-commercial use as
well as commercial; we are non-commercial.

## Attribution handling

Required attribution shape (per CC BY 4.0 best practice and CPIC's own
preferred citation format):

> "Pharmacogenomic recommendation adapted from CPIC guideline
> [<gene>-<drug>] (cpicpgx.org), CC BY 4.0."

For every guideline-text reuse (rendered prose, RedFlag rationale
sentences), the attribution string above must accompany the content,
either inline or in the Source citation footer. The OpenOnco render
layer already surfaces Source citations on every clinical claim, so
this requirement maps cleanly onto the existing pattern — no new
rendering work needed.

Data-table content (e.g. "DPYD c.1905+1G>A → no function") does not
require attribution per CC0, but we include the source-id `SRC-CPIC`
anyway for engineering traceability.

## Hosting mode

`referenced`, per `SOURCE_INGESTION_SPEC §1.4` default. We do not host
CPIC content in this repo; we cite by guideline ID and optionally fetch
the API on demand. Reasons:

1. CPIC updates ~quarterly; staying referenced avoids snapshot-stale
   risk.
2. The KB carries the mapping (gene-drug pair → CPIC guideline ID) but
   not the guideline's full prose, so re-hosting prose adds little.

If a future workstream needs offline rendering or guaranteed snapshots,
migration to `hosted` mode requires fresh review covering snapshot
cadence, attribution boilerplate (already drafted in
`src_cpic.yaml.attribution.text`), and storage scale (~350 pages
across ~30 guidelines).

## Engineering scope (this PR)

1. `knowledge_base/clients/cpic_client.py` — `BaseSourceClient` subclass.
   Live calls gated behind `OPENONCO_CPIC_LIVE=1`. Two query modes:
   `search_drug` (drug+gene pair lookup, the canonical use case) and
   `get_guideline` (by guideline ID).
2. `knowledge_base/hosted/content/sources/src_cpic.yaml` — Source entity
   with full license metadata (CC BY 4.0 + CC0 dual classification),
   `attribution.required: true`, `legal_review.status: reviewed`.
3. `tests/test_cpic_client.py` — 10 offline tests covering gate
   semantics, the DPYD-fluorouracil canonical query, PostgREST array
   wrapping, cache reuse, schema validation, source-id drift guard.
4. `tests/fixtures/cpic_responses/` — 2 stub JSON files (no CPIC
   content copied; derived from the public schema).

## NOT in scope (deliberately)

- **No RedFlag / Indication enrichment** in this PR. The DPYD-FOLFOX
  RedFlag is a separate workstream needing `CHARTER §6.1` two-reviewer
  signoff for the clinical content.
- **No live API calls by default.** `OPENONCO_CPIC_LIVE` must be set
  explicitly.
- **No `hosted` mode migration.**
- **No CI cron** for scheduled re-fetch.

## Re-review triggers

Update this doc and flip `legal_review.status` if any of:

1. CPIC switches the guideline license (e.g. tightens to CC BY-NC or
   adds NoDerivatives) — would invalidate the modification/commercial
   columns above.
2. OpenOnco adopts a commercial tier under `CHARTER §2` — would not
   change CC BY 4.0 applicability but might trigger a courtesy review
   with the CPIC team.
3. Migration to `hosted` mode — snapshotting + redistribution shape.
4. We start attributing per-RedFlag rather than per-render-block in a
   way that loses the CC BY 4.0 attribution propagation.

## Sign-off

- **Reviewer:** claude (self-review under `CHARTER §6.1` dev-mode
  exemption, v0.1 phase, per memory `project_charter_dev_mode_exemptions.md`).
- **Date:** 2026-05-18.
- **Notes:** CC BY 4.0 + CC0 is the cleanest possible license posture
  for a free-public-resource project. Attribution requirement maps
  onto the existing Source-citation render pattern with zero new
  infrastructure.
