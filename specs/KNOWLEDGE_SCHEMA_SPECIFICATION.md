# Knowledge Schema Specification

**Project:** OpenOnco
**Document:** Knowledge Schema Specification
**Version:** v0.1 (draft)
**Status:** Draft for discussion with the development team + Clinical Co-Leads
**Prerequisite documents:** CHARTER.md, CLINICAL_CONTENT_STANDARDS.md

---

> **Pivot 2026-04-27 — Actionability source.** The primary source for
> biomarker actionability has been migrated from **OncoKB** to **CIViC**.
> Rationale: the OncoKB Terms of Use explicitly prohibit use of the data
> "for patient services" and "generation of reports in a hospital or other
> patient care setting" — which is the exact definition of OpenOnco's
> scope (CHARTER §2). Audit details:
> [`docs/reviews/oncokb-public-civic-coverage-2026-04-27.md`](../docs/reviews/oncokb-public-civic-coverage-2026-04-27.md).
> CIViC (CC0) is now the primary actionability source; all engine modules
> have been given vendor-neutral names (`actionability_*`), which allows
> switching back to another source without rewriting the schema. The fields
> `oncokb_skip_reason` and other token vocabularies that do not affect
> render decisions are preserved unchanged (vocabulary stays).

---

## Purpose of this document

This document defines the **technical data structure of the knowledge base** —
which entities are stored, which fields are required, how entities are
related to each other, and how rules are represented in a format that can
be executed by the rule engine.

Without this document:
- Developers do not know which tables/collections to build
- Clinical Co-Leads have no format for submitting recommendations
- It is impossible to write an engine, a validator, or a migration script
- Each diagnosis is modeled ad-hoc, which destroys consistency

This document is the **contract between the clinical and technical layers**.

---

## 1. Modeling principles

### 1.1. Separation of knowledge and code

Rules, indications, and contraindications are in a declarative format
(YAML), not hardcoded in the code. The rule engine interprets the declaration.

**Motivation:** a clinician must be able to edit the knowledge base without
involving a developer. A change in an NCCN guideline → edit the YAML →
pull request → review → merge. No code changes.

### 1.2. Immutability through versioning

Each entity has a version. Old versions are stored forever (retention
policy in Charter §10). Update = new version, not overwrite.

### 1.3. Traceability

Each recommendation references sources (Tier 1–5 per CCS §2).
Dangling reference = invalid entity.

### 1.4. Explicit unknowns

"Unknown" is an `unknown` enum value, not `null`. The distinction
matters: null may mean "not filled in", unknown means "explicitly unknown
for this patient". The rule engine treats them differently.

### 1.5. Standards-based, not bespoke

We use standard vocabularies (SNOMED CT, LOINC, RxNorm, ICD-O-3) for
coding — we do not invent our own codes.

### 1.6. No composite scoring

The schema does not contain a `composite_rating` or `overall_score`.
Evidence level and strength of recommendation are stored separately
(per CCS §4).

---

## 2. Top-level entities (overview)

There are 12 core entities in total:

```
┌──────────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE BASE                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Disease ─────┐                                                   │
│               ├──── Indication ─────── Regimen ─────── Drug       │
│  Biomarker ──┤         │                   │                      │
│               │         │                   └── Contraindication  │
│  Stage  ─────┘         │                                          │
│                         │                                          │
│                         └── Source (evidence refs)                 │
│                                                                    │
│  RedFlag ─────────── (modifies Indication selection)              │
│                                                                    │
│  Test ────────────── (pre-treatment / monitoring)                  │
│                                                                    │
│  SupportiveCare ──── (linked to Regimen or RiskProfile)           │
│                                                                    │
│  MonitoringSchedule ─ (linked to Regimen + Phase)                 │
│                                                                    │
│  Algorithm ────────── (decision tree referencing Indications)     │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

The Patient entity is a separate layer (see Document 3: Data Standards /
mCODE). Here we model only knowledge, not patient data.

---

## 3. Entity: Disease

A diagnosis entity with WHO classification.

### 3.1. Schema

```yaml
# File: knowledge_base/diseases/hcv_mzl.yaml

entity_type: Disease
id: DIS-HCV-MZL
version: "1.0.0"
created: "2026-04-01"
last_reviewed: "2026-04-15"
reviewers: [reviewer-id-1, reviewer-id-2]

# Classification
names:
  preferred: "HCV-associated marginal zone lymphoma"
  ukrainian: "HCV-асоційована лімфома маргінальної зони"
  synonyms:
    - "HCV-related MZL"
    - "Hepatitis C-associated marginal zone lymphoma"
  abbreviations: ["HCV-MZL"]

codes:
  icd_o_3: "9699/3"
  icd_10: "C85.1"
  snomed_ct: "118605005"
  who_classification:
    edition: "5th"
    year: 2024
    entity: "Extranodal marginal zone lymphoma of mucosa-associated lymphoid tissue"
    category: "Mature B-cell neoplasms"

# Clinical characteristics
lineage: "B-cell"
cell_of_origin: "Marginal zone B-cell"
typical_sites:
  - "Spleen"
  - "Extranodal (MALT variants)"
  - "Lymph nodes (NMZL)"

# Etiological drivers (for archetype classification)
etiological_factors:
  - factor: "HCV chronic infection"
    strength: "causal"  # causal | associated | background
    source_refs: [SRC-FERRI-2008, SRC-ARCAINI-2016]

# Epidemiology (optional, for context)
epidemiology:
  incidence_global: "1-2 per 100,000/year (MZL overall)"
  hcv_mzl_proportion: "20-30% of NMZL in HCV-endemic regions"

# Archetype — determines document structure for this disease
archetype: "etiologically_driven"
# Valid values: etiologically_driven | biomarker_driven | stage_driven |
#               risk_stratified | line_of_therapy_sequential

# Linked entities
related_diseases:
  - {id: DIS-MZL-SPLENIC, relation: "variant"}
  - {id: DIS-DLBCL-TRANSFORMATION, relation: "can_transform_to"}

metadata:
  maintainer_domain: "hematologic_malignancies"
  priority_for_mvp: true
  notes: >
    First reference disease for the project. Chosen because it has
    well-defined etiological driver (HCV), clear guidelines (NCCN,
    ESMO, EASL), and reference document exists (HCV-MZL case V.0.0).
```

### 3.2. Required fields

- `entity_type`, `id`, `version`
- `names.preferred`
- `codes.icd_o_3` (required for all oncological entities)
- `codes.who_classification.entity`
- `lineage`
- `archetype`
- `last_reviewed`, `reviewers`

### 3.3. Archetype values

Based on CDSS architecture analysis (see project docs):

| Archetype | Meaning | Example diseases |
|---|---|---|
| `etiologically_driven` | Causal agent removal is part of treatment | HCV-MZL, MALT/H.pylori, HPV-OPC |
| `biomarker_driven` | Molecular profile primarily determines Rx | EGFR+ NSCLC, HER2+ BC, BRAF+ melanoma |
| `stage_driven` | Stage is primary therapy split | Early-stage breast, CRC |
| `risk_stratified` | Prognostic classification dominant | AML, CLL, multiple myeloma |
| `line_of_therapy_sequential` | Treatment = sequential lines | Metastatic NSCLC, mCRC 2L+ |

Archetype determines document template structure.

---

## 4. Entity: Biomarker

A molecular, histological, or laboratory marker.

### 4.1. Schema

```yaml
# File: knowledge_base/biomarkers/ki67.yaml

entity_type: Biomarker
id: BIO-KI67
version: "1.0.0"

names:
  preferred: "Ki-67"
  full_name: "Ki-67 proliferation index"
  alternative: "MIB-1"

codes:
  loinc: "85319-2"
  snomed_ct: "386030001"

# Type
biomarker_type: "protein_expression_ihc"
# Valid: mutation | fusion | amplification | deletion |
#         protein_expression_ihc | protein_expression_flow |
#         msi_status | tmb | methylation | chromosomal |
#         serum_marker | other

# Measurement
measurement:
  method: "immunohistochemistry"
  units: "percent"
  typical_range: [0, 100]
  rounding: "nearest 5%"

# Clinical interpretation cutoffs
# NOTE: cutoffs are disease-specific; stored in Indication entities,
# not here. This field shows general interpretation guidance.
interpretation_notes: >
  Proliferation index. Higher values indicate more rapidly dividing
  tumor. Cutoffs for clinical decisions vary by disease entity
  (e.g., ≥30% in some lymphomas triggers consideration of aggressive
  regimens; ≥20% in breast cancer correlates with luminal B subtype).

# Technical requirements
specimen_requirements:
  specimen_type: ["FFPE tissue", "Fresh frozen tissue"]
  minimum_cellularity: "sufficient tumor cells (>200 cells preferred)"

# Related biomarkers
related_biomarkers: []

last_reviewed: "2026-04-15"
reviewers: [reviewer-id]
```

### 4.2. Example: mutation biomarker

```yaml
entity_type: Biomarker
id: BIO-EGFR-L858R
names:
  preferred: "EGFR L858R"
  full_name: "Epidermal Growth Factor Receptor, exon 21, L858R mutation"
codes:
  hgvs_protein: "NP_005219.2:p.Leu858Arg"
  hgvs_coding: "NM_005228.5:c.2573T>G"
  oncokb_id: "EGFR_L858R"

biomarker_type: "mutation"
mutation_details:
  gene: "EGFR"
  gene_hugo_id: "3236"
  exon: 21
  type: "missense"
  functional_impact: "activating"

measurement:
  method: ["NGS panel", "PCR-based specific assay"]
  sensitivity_requirement: "allele frequency ≥5% typically detectable"

# OncoKB reference
knowledge_base_ref:
  oncokb: "https://oncokb.org/gene/EGFR/L858R"
  civic: "https://civicdb.org/links/variants/33"
  last_synced: "2026-04-15"
```

### 4.3. Actionability-wiring fields (Phase 1 scaffolding)

Three optional fields have been added to Biomarker to safely connect an
external biomarker-actionability database (CIViC in v0.1 after the
2026-04-27 pivot — see the callout at the top of this document). The
fields are deliberately vendor-neutral in name — the engine switches from
OncoKB to CIViC without any schema change. This is a purely engineering
extension of the schema; this version does not touch any clinical content
in `bio_*.yaml` — field population is performed in phase 2.

#### `actionability_lookup` (optional)

An explicit hint that allows the actionability extractor to query the
annotation for this specific biomarker in the external KB (CIViC). If
the field is absent, the extractor **skips** the biomarker entirely —
this is intentional, to avoid silently "guessing" (gene, variant) from
the id, which risks giving the clinician a false negative.

The field was previously named `oncokb_lookup` (Phase 1 scaffolding);
renamed to `actionability_lookup` in the Phase 1.5 migration (commit
`c72e45b`, 2026-04-27) together with the CIViC pivot. Semantics and
accepted forms are unchanged.

```yaml
actionability_lookup:
  gene: "BRAF"            # HGNC symbol, uppercase, 1..32 chars
  variant: "V600E"        # short HGVS-p / structural descriptor / fs
```

Accepted forms for `variant`:
- Short HGVS-p: `V600E`, `L858R`, `G12C`
- Structural: `Exon 19 deletion`, `E746_A750del`
- Frameshift tokens: `W288fs`
- CIViC fusion notation: `BCR::ABL1` (gene pair separated by `::`),
  including with nested resistance mutations in `variant`
  (`Fusion AND ABL1 T315I`)

Full HGVS validation lives in `engine/civic_variant_matcher.py`
(previously `engine/oncokb_extract.py:normalize_variant`). The schema
performs only a type check.

#### `oncokb_skip_reason` (optional)

A stable machine-readable token explaining why a biomarker is
intentionally **excluded** from actionability queries. The field name is
preserved for historical reasons (the token vocabulary is source-agnostic
— the same exclusion reasons apply to both CIViC and OncoKB). These
strings are grep-stable — downstream code (`engine/_actionability.py`)
keys behavior on them, so renaming without coordination is prohibited.

Permitted values (`Literal`):

| Token | When used |
|---|---|
| `ihc_no_variant` | IHC without a molecular variant (Ki-67, CD20, …) |
| `score` | Score/index (IPI, MIPI, GIPSS) |
| `clinical_composite` | Composite clinical marker |
| `serological` | Serology (HCV-Ab, HBsAg) |
| `viral_load` | Viral load (HCV-RNA, HBV-DNA) |
| `tumor_marker` | General tumor marker (CA-125, AFP, β-hCG) |
| `imaging` | Imaging pattern |
| `germline_no_somatic` | Germline-only variant, without somatic actionability |
| `fusion_mvp` | Fusion — outside MVP scope |
| `itd_mvp` | ITD variants (FLT3-ITD) — outside MVP scope |
| `multi_allele_mvp` | Multi-allelic cases — outside MVP scope |
| `tumor_agnostic` | Tumor-agnostic indication — separate pathway |

Mutually exclusive with `actionability_lookup`. Valid states: "neither
set" (biomarker not yet triaged), "lookup only", "skip_reason only". Both
simultaneously → ValidationError.

#### `external_ids` (optional)

Cross-references to external KBs. All keys are optional; partial
population (e.g., only `hgnc_symbol`) is fine.

```yaml
external_ids:
  hgnc_symbol: "EGFR"
  hgnc_id: "HGNC:3236"
  oncokb_url: "https://oncokb.org/gene/EGFR/L858R"
  civic_id: "33"
  civic_url: "https://civicdb.org/links/variants/33"
  clingen_id: "CA123456"
  hgvs_protein: "NP_005219.2:p.Leu858Arg"
  hgvs_coding: "NM_005228.5:c.2573T>G"
```

This field is independent of `actionability_lookup` / `oncokb_skip_reason`
— it may be populated in any combination. `oncokb_url` is retained in the
vocabulary as read-only legacy metadata: the render layer does not use it
(see §4.4 for OncoKB ToS restrictions), but citations from published
scientific works may reference a stable OncoKB page without redistribution
conflict.

---

### 4.4. Entity: BiomarkerActionability (BMA)

A separate entity that maps a (gene-variant, tumor type) pair to a
clinical actionability tier per ESCAT (ESMO Scale for Clinical
Actionability of molecular Targets, Mateo 2018). It composes existing
`BIO-*` (gene/variant taxonomy) and `DIS-*` (disease taxonomy) into a
per-tumor clinical interpretation. Pydantic schema:
`knowledge_base/schemas/biomarker_actionability.py`.

**ID convention:** `BMA-{biomarker}-{variant?}-{disease}`, for example
`BMA-BRAF-V600E-CRC`, `BMA-EGFR-T790M-NSCLC`. The `biomarker_id` may
already encode the variant (e.g. `BIO-BRAF-V600E`); in that case,
`variant_qualifier` is an optional refinement (sub-variant / co-occurrence).
`null` in `variant_qualifier` → gene-level cell (any pathogenic alteration
is treated identically).

#### 4.4.1. Canonical schema (post-pivot)

```yaml
# File: knowledge_base/hosted/content/biomarker_actionability/bma_braf_v600e_crc.yaml

entity_type: BiomarkerActionability
id: BMA-BRAF-V600E-CRC
biomarker_id: BIO-BRAF-V600E         # FK → BIO-*
variant_qualifier: null               # null → entire variant encoded in biomarker_id
disease_id: DIS-CRC                  # FK → DIS-*

# ── Primary actionability tier (vendor-neutral) ────────────────────────
escat_tier: "IA"                     # ESCAT IA|IB|IIA|IIB|IIIA|IIIB|IV|X

# ── Evidence sources block (canonical post-pivot) ──────────────────────
# Replaces legacy fields oncokb_level / oncokb_snapshot_version. A list
# of EvidenceSourceRef structures; no source is privileged in render.
evidence_sources:
  - source: "SRC-CIVIC"              # FK → Source entity
    level: "B"                       # CIViC level: A|B|C|D|E
    evidence_ids: ["civic:EID-1409", "civic:EID-7821"]
    direction: "supports"            # supports | does_not_support | n/a
    significance: "sensitivity_response"  # sensitivity_response|resistance|reduced_sensitivity|...
    note: "Encorafenib + cetuximab in BRAF V600E mCRC after prior therapy."
  - source: "SRC-NCCN-COLORECTAL-2025"
    level: "category_1"              # NCCN-specific level vocabulary
    evidence_ids: []
    direction: "supports"
    significance: "sensitivity_response"
    note: "Preferred 2L+ regimen for V600E."

# ── Two-reviewer gate flag (CHARTER §6.1) ─────────────────────────────
# True → blocks publish until two clinical sign-offs. Set by the loader
# if drafted_by starts with "claude_extraction" or if evidence_sources
# contains only A/B without guideline corroboration.
actionability_review_required: true

# ── Per-jurisdiction regulatory ─────────────────────────────────────
regulatory_approval:
  fda: ["encorafenib + cetuximab — BRAF V600E mCRC (FDA 2020)"]
  ema: ["encorafenib + cetuximab — BRAF V600E mCRC (EMA 2020)"]
  ukraine: []

recommended_combinations:
  - "encorafenib + cetuximab (2L+ V600E mCRC per SRC-NCCN-COLORECTAL-2025)"
contraindicated_monotherapy:
  - "BRAF inhibitor monotherapy (paradoxical MAPK activation)"

primary_sources:                      # ≥1 required (loader-enforced)
  - SRC-NCCN-COLORECTAL-2025
  - SRC-CIVIC
last_verified: "2026-04-27"
reviewer_signoffs: []                 # ≥2 to publish per CHARTER §6.1
notes: >
  ESCAT IA. Resistance: MAPK reactivation through MEK or PI3K — see
  triplet trials.
```

#### 4.4.2. `EvidenceSourceRef` shape

```
EvidenceSourceRef = {
  source:        str,        # FK → SRC-*  (required)
  level:         str,        # source-specific level token (required)
  evidence_ids:  list[str],  # source-native IDs, e.g. "civic:EID-1409"
  direction:     "supports" | "does_not_support" | "n/a",
  significance:  str,        # "sensitivity_response" | "resistance" |
                             # "reduced_sensitivity" | "predisposition" |
                             # "better_outcome" | "poor_outcome" | ...
  note:          Optional[str],
}
```

`level` is a **source-native token** (CIViC `A|B|C|D|E`, NCCN
`category_1|2A|2B|3`, ESMO `I|II|III|IV|V`). Vendor mapping (e.g.,
CIViC-A → ESCAT IA) lives in the render layer, not in the YAML —
clinical responsibility for the cumulative tier (`escat_tier`) rests
with the BMA reviewer, not with automated mapping.

The field `direction == "does_not_support"` is load-bearing: the render
must display such an entry as an **anti-evidence card** (negative
recommendation), not suppress it. CIViC contains ~10% such entries —
this is an intentional clinical signal that the engine must not silently
drop.

#### 4.4.3. `escat_tier` as the primary actionability tier

`escat_tier` is vendor-neutral and publication-stable (Mateo 2018 does
not update daily, unlike the OncoKB level scheme). This field is what
the render uses as the primary tier in Plan cards. The individual
`evidence_sources[*].level` fields are the evidence base for sign-off,
not a user-facing render token.

#### 4.4.4. Legacy fields and ToS restrictions

The fields `oncokb_level` and `oncokb_snapshot_version` that existed in
Phase 0 draft YAMLs have been **removed from the schema** in the Phase
1.5 migration (engine commit `5384348`, YAML schema migration — pending
Part B). If an entry in `evidence_sources` has `source: "SRC-ONCOKB"`,
it is treated by the render layer as **legacy metadata**: it is not
surfaced in the user UI and is not used as the basis for a
recommendation. Rationale: OncoKB Terms of Use (Phase-4 render rule;
details in `SOURCE_INGESTION_SPEC.md` §2.5 and
`docs/reviews/oncokb-public-civic-coverage-2026-04-27.md` §3.3).

#### 4.4.5. Formalization status

The entity was added to the Pydantic schema
(`knowledge_base/schemas/biomarker_actionability.py`) on 2026-04-26
under the CSD Lab pitch and did not appear in the §2 top-level entities
in the v0.1 draft of this document. This section anchors BMA as a
full-fledged 13th-tier entity for a future revision of §2 and the
data-model diagram (§15).

---

## 5. Entity: Drug

An individual drug.

### 5.1. Schema

```yaml
# File: knowledge_base/drugs/rituximab.yaml

entity_type: Drug
id: DRUG-RITUXIMAB
version: "1.0.0"

names:
  generic: "rituximab"
  ukrainian: "ритуксимаб"
  brand_names: ["Rituxan", "MabThera", "Truxima (biosimilar)", "Ruxience (biosimilar)"]
  atc_code: "L01FA01"
  inn: "rituximab"

codes:
  rxnorm: "121191"
  snomed_ct: "386919002"
  ndc: []  # multiple; per-formulation basis

# Drug class
drug_class:
  primary: "monoclonal_antibody"
  mechanism: "anti-CD20 monoclonal antibody"
  target: "CD20 (B-cell surface marker)"

# Regulatory status
regulatory_status:
  fda:
    approved: true
    first_approval_year: 1997
    indications_link: ["NCCN-B-Cell-Lymphomas", "multiple"]
  ema:
    approved: true
  ukraine_registration:
    registered: true
    registration_number: "[filled by UA regulatory lookup]"
    reimbursed_nszu: true
    reimbursement_indications: ["specific - see НСЗУ list"]

# Dosing (generic; disease-specific doses in Regimen entity)
typical_dosing:
  standard_dose: "375 mg/m²"
  standard_route: "intravenous infusion"
  notes: >
    Dose varies by disease and line of therapy. See Regimen entities
    for disease-specific dosing. Infusion rate protocols apply.

# Formulations available
formulations:
  - {form: "solution_for_infusion", strength: "10 mg/mL", volumes: ["10 mL", "50 mL"]}
  - {form: "subcutaneous_injection", strength: "120 mg/mL", note: "1400 mg fixed dose"}

# Contraindications (general; disease-specific in Contraindication entity)
absolute_contraindications:
  - "Known severe hypersensitivity to rituximab or murine proteins"
  - "Active severe infection"

# Safety warnings
black_box_warnings:
  - warning: "Fatal infusion reactions"
    source: "FDA label, updated 2024"
  - warning: "Severe mucocutaneous reactions"
    source: "FDA label"
  - warning: "Hepatitis B reactivation"
    source: "FDA label"
  - warning: "Progressive multifocal leukoencephalopathy (PML)"
    source: "FDA label"

# Important drug interactions
interactions:
  - with: "live vaccines"
    severity: "contraindicated"
    mechanism: "immune suppression reduces immune response"

# Key toxicities
common_adverse_events:
  - {event: "infusion_reaction", frequency: "10-20%", grade: "typically 1-2"}
  - {event: "neutropenia", frequency: "15-30%", grade: "3-4: 5-10%"}
  - {event: "infection", frequency: "variable"}
  - {event: "tumor_lysis_syndrome", frequency: "rare; depends on disease burden"}

# Pharmacology
pharmacology:
  half_life_days: [11, 30]  # range
  elimination: "Reticuloendothelial system; not renal"
  crosses_bbb: false

source_refs: [SRC-RITUXIMAB-FDA-LABEL, SRC-NCCN-BCELL-V2-2026]

last_reviewed: "2026-04-15"
reviewers: [reviewer-id-1, reviewer-id-2]
```

### 5.2. Required fields

- `id`, `names.generic`, `names.ukrainian`
- `drug_class.mechanism`
- `regulatory_status.ukraine_registration.registered`
- `absolute_contraindications`
- At least one `source_refs`

---

## 6. Entity: Regimen

A treatment regimen — a combination of drugs with a schedule.

> **Change 2026-04-29 — phase-aware schema (PR1 of regimen-phases-refactor).**
> Optional fields `phases:` (`list[RegimenPhase]`) and
> `bridging_options:` (`list[regimen_id]`) have been added. `components:`
> remains; for legacy YAMLs without `phases:` the loader auto-wraps
> `components` into a single phase `name: "main"`. Details — §6.4 below.
> Plan: [`docs/reviews/regimen-phases-refactor-plan-2026-04-28.md`](../docs/reviews/regimen-phases-refactor-plan-2026-04-28.md).
> Manual YAML migration (18 CAR-T/TIL/SCT/multi-block files) — separate PR2.

### 6.1. Schema

```yaml
# File: knowledge_base/regimens/br.yaml

entity_type: Regimen
id: REG-BR-LYMPHOMA
version: "1.0.0"

names:
  preferred: "Bendamustine-Rituximab (BR)"
  acronym: "BR"
  ukrainian: "Бендамустин + Ритуксимаб (BR)"

# Components — flat list, kept for back-compat. New phase-aware regimens
# may also author the `phases:` block below; legacy YAMLs without
# `phases:` are auto-wrapped by the loader into a single "main" phase.
components:
  - drug_id: DRUG-BENDAMUSTINE
    dose: "90 mg/m²"
    route: "intravenous"
    schedule: "days 1-2 of each cycle"
    order: 1
  - drug_id: DRUG-RITUXIMAB
    dose: "375 mg/m²"
    route: "intravenous"
    schedule: "day 1 of each cycle"
    order: 2
    notes: "May be given as day 0 per institutional protocol"

# Phases (added 2026-04-29). Optional. Render layer iterates this when
# present, otherwise falls back to auto-wrap of `components` into a
# single phase named "main". See §6.4 for shape + vocabulary.
# Example (multi-phase axi-cel CAR-T):
#
# phases:
#   - name: lymphodepletion
#     purpose_ua: "виснаження лімфоцитів перед CAR-T для приживлення клітин"
#     duration: "3 days, days -5 to -3"
#     timing_relative_to: main_infusion
#     timing_offset_days: -5
#     optional: false
#     components:
#       - drug_id: DRUG-CYCLOPHOSPHAMIDE
#         dose: "500 mg/m²/day"
#         schedule: "IV days -5, -4, -3"
#         route: IV
#       - drug_id: DRUG-FLUDARABINE
#         dose: "30 mg/m²/day"
#         schedule: "IV days -5, -4, -3"
#         route: IV
#   - name: main
#     purpose_ua: "основна терапія — інфузія CAR-T"
#     components:
#       - drug_id: DRUG-AXICABTAGENE-CILOLEUCEL
#         schedule: "Single IV infusion day 0"
#         route: IV

# Bridging options (added 2026-04-29). For therapies with a manufacturing
# window (CAR-T, TIL): list of acceptable bridging Regimen IDs. Render
# surfaces these as a separate "Якщо очікування на основну терапію >2 тижні"
# section. Empty list → no bridging structurally available.
bridging_options: []

# Cycle structure
cycle_length_days: 28
total_cycles: 6
total_duration_weeks: 24

# Intent
typical_intent: ["curative", "palliative"]
# Specific intent determined per Indication

# Dose modifications
dose_adjustments:
  - condition: "FIB-4 > 3.25 OR cirrhosis"
    modification: "Reduce bendamustine to 70 mg/m²"
    rationale: "Hepatic dysfunction increases bendamustine toxicity"
    source_refs: [SRC-EMA-BENDAMUSTINE-SmPC]
  - condition: "ECOG >= 2 OR age >= 75"
    modification: "Consider bendamustine 70-80 mg/m²"
    rationale: "Reduced tolerance in frail patients"
  - condition: "CrCl < 30 mL/min"
    modification: "Not recommended; use alternative regimen"

# Toxicity profile (summary)
toxicity_profile:
  myelosuppression: "moderate-severe"
  cardiotoxicity: "low"
  neurotoxicity: "low"
  hepatotoxicity: "moderate"
  nephrotoxicity: "low"
  alopecia: "moderate"
  emetogenic_risk: "moderate"
  treatment_related_mortality_percent: [1, 2]

# Required premedication
premedication:
  rituximab:
    - "paracetamol 1000 mg PO"
    - "diphenhydramine 25-50 mg PO or IV"
    - "methylprednisolone 100 mg IV (or equivalent)"
  bendamustine:
    - "ondansetron 8 mg IV or equivalent 5-HT3 antagonist"
    - "dexamethasone 8-12 mg IV"

# Required supportive care
mandatory_supportive_care:
  - id: SUPP-PJP-PROPHYLAXIS
    notes: "Cotrimoxazole 480 mg daily during treatment + 6 months"
  - id: SUPP-ANTIVIRAL-PROPHYLAXIS
    notes: "Acyclovir 400 mg BID during treatment + 6 months"
  - id: SUPP-HBV-SCREENING-PROPHYLAXIS
    notes: "Required per CCS §3 — see Contraindication CONTRA-HBV"

# Monitoring during regimen
monitoring_schedule_id: MON-BR-STANDARD

# Ukraine availability
ukraine_availability:
  bendamustine:
    registered: true
    reimbursed_nszu: true  # verify current
    typical_cost_per_cycle_uah: "[to fill from pricing analysis]"
  rituximab:
    registered: true
    reimbursed_nszu: true
    biosimilar_available: true

source_refs:
  - SRC-NCCN-BCELL-V2-2026
  - SRC-ESMO-MZL-2020
  - SRC-BRIGHT-TRIAL-FLINN-2019
  - SRC-STIL-NHL1-RUMMEL-2013

last_reviewed: "2026-04-15"
reviewers: [reviewer-id-hem-1, reviewer-id-hem-2]
```

### 6.2. Required fields

- `id`, `names.preferred`, `names.ukrainian`
- `components` (list with at least one Drug)
- `cycle_length_days`
- `total_cycles` OR `total_duration_weeks`
- `toxicity_profile`
- `monitoring_schedule_id`
- At least one `source_refs`

### 6.3. Toxicity profile values

For each toxicity category, use enum:
- `none`
- `low`
- `moderate`
- `severe`
- `variable` (with description in `notes`)

Numeric rates (where available) in separate fields with source.

### 6.4. RegimenPhase (added 2026-04-29)

Phase-aware decomposition of a course of therapy. Closes a structural
gap identified in patient-zero feedback: "why did the plan not show
cyclophosphamide *before* the main therapy?" — lymphodepletion / bridging
/ conditioning / IL-2 support were previously hidden inside the details
of a one-block render via the flat `components` + string `premedication`.
Plan: [`docs/reviews/regimen-phases-refactor-plan-2026-04-28.md`](../docs/reviews/regimen-phases-refactor-plan-2026-04-28.md).

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | str | Phase name (open string; curator-facing vocabulary below) |
| `purpose_ua` | str | Ukrainian description of the phase purpose for render (e.g., "lymphocyte depletion before CAR-T") |
| `purpose_en` | Optional[str] | English description (optional) |
| `components` | list[RegimenComponent] | Drug components for this phase only |
| `duration` | Optional[str] | Duration, e.g. "3 days, days -5 to -3" |
| `timing_relative_to` | Optional[str] | `main_infusion` \| `next_phase` \| `absolute` \| `previous_phase_completion` |
| `timing_offset_days` | Optional[int] | Offset in days; `-5` = "5 days before main_infusion" |
| `optional` | bool | bridging — `true`; lymphodepletion — `false` |
| `sources` | list[str] | Source IDs documenting this phase |

**Curator-facing vocabulary for `name`:**

```
lymphodepletion | bridging | induction | consolidation | maintenance |
main | premedication | conditioning | salvage_induction |
alternating_block_a | alternating_block_b | il2_support
```

The schema does not enum this yet — PR1 keeps `name: str` because new
cases will emerge during the PR2 manual migration. If the vocabulary
stabilizes — close it with an enum in the next PR.

### 6.5. Back-compat invariant (auto-wrap)

All legacy YAMLs without `phases:` will, after loading, have
`regimen.phases == [RegimenPhase(name="main", purpose_ua="main therapy",
components=regimen.components)]`. `regimen.components` remains non-empty
and matches `regimen.phases[0].components` for legacy YAMLs.

The logic lives in a Pydantic `@model_validator(mode="after")` on the
`Regimen` class (`knowledge_base/schemas/regimen.py`). The loader
inherits this behavior automatically via `Regimen.model_validate(raw)`.

**Contracts:**

- If `phases:` is explicitly authored — auto-wrap does NOT fire. `phases`
  and `components` remain independent on input.
- If `components:` is empty — `phases:` is also empty. The render layer
  must route such entities separately (e.g., a surveillance-only
  "regimen" `REG-DAA-OBSERVATION-HCV-MZL`).
- `regimen.components` is NOT deprecated. We do not plan to remove it
  in PR1/PR2.

Coverage: `tests/test_regimen_phases.py` (10 tests, including a catch-all
over all 244 regimen YAMLs).

### 6.6. bridging_options

`Regimen.bridging_options: list[str]` — a list of regimen IDs acceptable
as bridging therapy during the manufacturing window for CAR-T / TIL.
Default — empty list. The render layer (PR2) surfaces this block as a
separate section "If wait for the main therapy exceeds 2 weeks". Filling
this in for existing CAR-T/TIL regimens is part of the PR2 manual
migration.

---

## 7. Entity: Indication

**The most important entity.** Connects Disease + clinical profile →
Regimen with a level of evidence.

### 7.1. Schema

```yaml
# File: knowledge_base/indications/hcv_mzl_1l_standard.yaml

entity_type: Indication
id: IND-HCV-MZL-1L-STANDARD
version: "1.0.0"

# What clinical scenario this covers
applicable_to:
  disease_id: DIS-HCV-MZL
  line_of_therapy: 1  # 1 = first-line; 2 = second-line; etc.
  stage_requirements:
    stages: ["all"]  # or specific: ["I-II", "III-IV"]
  biomarker_requirements:
    required:
      - biomarker_id: BIO-HCV-RNA-POSITIVE
        value_constraint: "positive"
    excluded:
      - biomarker_id: BIO-TRANSFORMATION-MARKERS
        value_constraint: "negative"
  demographic_constraints:
    age_range: [18, null]  # null = no upper limit
    performance_status_max: 2  # ECOG
  additional_constraints:
    - "No red flags for histological transformation"

# The recommendation
recommended_regimen_id: REG-BR-LYMPHOMA
concurrent_therapy:
  - regimen_id: REG-DAA-SOFOSBUVIR-VELPATASVIR
    timing: "concurrent_with_br"
    rationale: "HCV eradication removes antigenic driver; safe co-administration confirmed"

# Sequential/maintenance phase
followed_by:
  - regimen_id: REG-RITUXIMAB-MAINTENANCE
    timing: "after_completion_of_induction"
    duration: "2 years (q8w × 12 doses)"
    rationale: "BRIGHT trial: EFS 81% → 94% with maintenance"

# Evidence assessment (per CCS §4)
evidence_level: "moderate"
# high | moderate | low | very_low
evidence_level_rationale: >
  Phase 2 BArT trial (Arcaini 2014, N=44); supported by retrospective
  analyses and aligned with NCCN/ESMO recommendations. No Phase 3 RCT
  specifically for HCV-MZL 1L (HCV-MZL too rare for dedicated Phase 3).

strength_of_recommendation: "preferred"
# preferred | alternative | not_recommended | insufficient_evidence
strength_rationale: >
  Consensus across NCCN, ESMO, and EASL recommendations. Benefit-harm
  balance clearly favorable in appropriate population. Lower toxicity
  than historical R-CHOP with equivalent efficacy in non-transformed MZL.

nccn_category: "2A"  # 1 | 2A | 2B | 3 | N/A

# Expected outcomes (key evidence numbers)
expected_outcomes:
  overall_response_rate:
    value: "85-90%"
    source_ref: SRC-BRIGHT-TRIAL
    notes: "For BR in indolent lymphomas broadly"
  complete_response:
    value: "~60%"
    source_ref: SRC-BRIGHT-TRIAL
  progression_free_survival:
    median_months: 42
    source_ref: SRC-BRIGHT-TRIAL
    note: "For indolent NHL; HCV-MZL-specific data limited"
  hcv_cure_rate_svr12:
    value: "95-98%"
    source_ref: SRC-EASL-HCV-2023
  overall_survival_5y:
    value: "80-85%"
    source_ref: SRC-ARCAINI-2016

# Contraindications (hard)
hard_contraindications: [CONTRA-AMIODARONE-SOFOSBUVIR, CONTRA-HBV-NO-PROPHYLAXIS]

# Red flags that should trigger alternative indication
red_flags_triggering_alternative:
  - red_flag_id: RF-B-SYMPTOMS
    alternative_indication: IND-HCV-MZL-1L-AGGRESSIVE
  - red_flag_id: RF-LDH-HIGH
    alternative_indication: IND-HCV-MZL-1L-AGGRESSIVE
  - red_flag_id: RF-BULKY-DISEASE
    alternative_indication: IND-HCV-MZL-1L-AGGRESSIVE
  - red_flag_id: RF-RAPID-PROGRESSION
    alternative_indication: IND-HCV-MZL-1L-AGGRESSIVE

# Pre-treatment workup
required_tests: [TEST-CBC, TEST-LFT-COMPREHENSIVE, TEST-HCV-RNA-QUANT, TEST-HBV-SEROLOGY, TEST-FIB-4]
desired_tests: [TEST-ECHO-LVEF, TEST-LDH, TEST-B2-MICROGLOBULIN]

# Sources
sources:
  - id: SRC-NCCN-BCELL-V2-2026
    section: "MZL-3, MZL-4"
    weight: "primary"
  - id: SRC-ESMO-MZL-2020
    weight: "primary"
  - id: SRC-EASL-HCV-2023
    weight: "primary_for_daa_component"
  - id: SRC-BART-ARCAINI-2014
    weight: "supporting_phase2"
  - id: SRC-BRIGHT-FLINN-2019
    weight: "supporting_phase3_indolent_broad"

# Controversies (per CCS §1.2 — show, don't hide)
known_controversies:
  - topic: "Bendamustine dosing in elderly/cirrhotic"
    positions:
      - "NCCN: 90 mg/m² standard"
      - "ESMO: consider 70 mg/m² for elderly/cirrhotic"
    resolution: "Implemented as dose_adjustment in Regimen"

last_reviewed: "2026-04-15"
reviewers: [reviewer-id-hem-1, reviewer-id-hem-2]
```

### 7.2. Required fields

- `id`, `version`
- `applicable_to.disease_id`, `applicable_to.line_of_therapy`
- `recommended_regimen_id`
- `evidence_level`, `strength_of_recommendation`
- `hard_contraindications` (may be empty array)
- Minimum 2 `sources` of Tier 1 or Tier 2 (per CCS §6.1)

### 7.3. The two-plan architecture

For the project's core use case (generating two alternative plans),
pairs of Indications are created:

```
IND-HCV-MZL-1L-STANDARD   (less intensive)
IND-HCV-MZL-1L-AGGRESSIVE (more intensive)
```

Linked by shared `applicable_to` but different `recommended_regimen_id`
and `red_flags_triggering_alternative` bidirectionally.

Algorithm entity (§12) determines which is "default" vs "alternative"
for a given patient.

---

## 8. Entity: Contraindication

Hard rules that prevent regimen use.

### 8.1. Schema

```yaml
# File: knowledge_base/contraindications/amiodarone_sofosbuvir.yaml

entity_type: Contraindication
id: CONTRA-AMIODARONE-SOFOSBUVIR
version: "1.0.0"

# Severity
severity: "absolute"
# absolute | relative | caution

# Trigger condition (machine-readable)
trigger:
  type: "drug_drug_interaction"
  conditions:
    - patient_current_medication_includes: DRUG-AMIODARONE
    - proposed_regimen_contains: DRUG-SOFOSBUVIR
  logic: "AND"  # all conditions must be true

# Human-readable description
description:
  english: >
    Concurrent use of sofosbuvir and amiodarone can cause severe,
    potentially fatal bradyarrhythmia. This combination is absolutely
    contraindicated.
  ukrainian: >
    Одночасне використання софосбувіру та аміодарону може спричинити
    важку, потенційно фатальну брадиаритмію. Ця комбінація абсолютно
    протипоказана.

# What to do instead
alternative_actions:
  - "Use DAA combination that does not include sofosbuvir (e.g., glecaprevir/pibrentasvir)"
  - "If sofosbuvir essential, discontinue amiodarone ≥6 months before (long half-life)"
  - "Consult cardiology for amiodarone alternatives"

# Sources
sources:
  - id: SRC-FDA-SOFOSBUVIR-LABEL
    section: "Boxed Warning"
  - id: SRC-BACK-2015-DRUG-INTERACTION

# Related entities
affects_indications:
  - IND-HCV-MZL-1L-STANDARD
  - IND-HCV-MZL-1L-AGGRESSIVE
  - IND-HCV-ANY-WITH-SOFOSBUVIR  # generic

last_reviewed: "2026-04-15"
reviewers: [reviewer-id-pharm, reviewer-id-hem]
```

### 8.2. Severity levels

| Severity | Meaning | Engine behavior |
|---|---|---|
| `absolute` | Never proceed with this combination | Regimen excluded; show hard block |
| `relative` | Proceed only with specific precautions | Show warning; require acknowledgment |
| `caution` | Proceed with monitoring | Show informational note |

### 8.3. Trigger types

- `patient_condition` — patient has specific diagnosis/status
- `lab_value` — lab value outside range
- `medication` — patient on specific drug
- `drug_drug_interaction` — proposed + existing drug conflict
- `allergy` — documented allergy
- `prior_treatment` — specific prior treatment history
- `biomarker_status` — specific biomarker value/absence
- `demographic` — age/sex-specific

---

## 9. Entity: RedFlag

Clinical findings that shift treatment intensity choice.

### 9.1. Schema

```yaml
# File: knowledge_base/red_flags/b_symptoms.yaml

entity_type: RedFlag
id: RF-B-SYMPTOMS
version: "1.0.0"

names:
  preferred: "B symptoms"
  ukrainian: "B-симптоми"

# What defines it
definition:
  english: >
    Constitutional symptoms of lymphoma including: unexplained fever >38°C,
    drenching night sweats, or unexplained weight loss >10% body weight
    over 6 months.
  ukrainian: >
    Загальні симптоми лімфоми: незрозуміла лихоманка >38°C, нічна
    пітливість, втрата ваги >10% за 6 місяців.

# Trigger (machine-readable)
trigger:
  type: "symptom_composite"
  any_of:
    - {symptom: "fever_unexplained", threshold_celsius: 38.0, duration: ">2 weeks"}
    - {symptom: "night_sweats_drenching"}
    - {symptom: "weight_loss_unexplained", threshold_percent: 10, duration_months: 6}

# Clinical implication
clinical_direction: "intensify"
# intensify | de_escalate | hold | investigate

# Which diseases this is relevant to
relevant_diseases: [DIS-HCV-MZL, DIS-DLBCL, DIS-FOLLICULAR-LYMPHOMA, DIS-HODGKIN]

# In MVP: linked to alternative indication logic
shifts_algorithm:
  from_indication: IND-HCV-MZL-1L-STANDARD
  to_indication: IND-HCV-MZL-1L-AGGRESSIVE
  strength: "strong_indication_to_shift"
  # strong_indication_to_shift | consider_shift | weak_signal

source_refs: [SRC-LUGANO-CLASSIFICATION, SRC-NCCN-BCELL-V2-2026]
last_reviewed: "2026-04-15"
reviewers: [reviewer-id]
```

---

## 10. Entity: Test

Clinical tests — pre-treatment workup and monitoring.

### 10.1. Schema

```yaml
# File: knowledge_base/tests/hcv_rna_quant.yaml

entity_type: Test
id: TEST-HCV-RNA-QUANT
version: "1.0.0"

names:
  preferred: "HCV RNA quantitative PCR"
  ukrainian: "HCV-RNA ПЛР кількісний"

codes:
  loinc: "11011-4"

category: "virology"
# hematology | biochemistry | virology | immunology | imaging |
# pathology | molecular | cardiac | other

purpose:
  - "Baseline HCV viral load before DAA treatment"
  - "Monitoring response to DAA"
  - "Detection of SVR12 (sustained virologic response)"

specimen:
  type: "blood"
  volume_ml: 5
  tube: "EDTA or SST"

turnaround_time_business_days: [2, 5]

priority_class: "critical"
# critical | standard | desired | calculation_based

availability_ukraine:
  state_funded: true
  typical_cost_uah: "[estimate; varies]"
  typical_availability: "widely available in oncology centers"

linked_to_regimens: [REG-DAA-SOFOSBUVIR-VELPATASVIR]
linked_to_diseases: [DIS-HCV-MZL, DIS-HCV-DLBCL, DIS-HCV-ANY]

source_refs: [SRC-EASL-HCV-2023]
last_reviewed: "2026-04-15"
reviewers: [reviewer-id]
```

### 10.2. Priority classes

Follows HCV-MZL reference document convention:
- `critical` — must have before treatment decision
- `standard` — routine part of workup
- `desired` — helpful but not blocking
- `calculation_based` — derived from other tests (e.g., FIB-4, BSA)

---

## 11. Entity: SupportiveCare

Prophylactic and supportive interventions.

### 11.1. Schema

```yaml
# File: knowledge_base/supportive_care/pjp_prophylaxis.yaml

entity_type: SupportiveCare
id: SUPP-PJP-PROPHYLAXIS
version: "1.0.0"

names:
  preferred: "PJP (Pneumocystis jirovecii) prophylaxis"
  ukrainian: "Профілактика пневмоцистної пневмонії"

intervention_type: "pharmacological"
# pharmacological | procedural | nutritional | psychosocial | monitoring

# What
standard_intervention:
  drug_id: DRUG-COTRIMOXAZOLE
  dose: "480 mg once daily OR 960 mg three times weekly"
  route: "oral"
  duration: "during_immunosuppressive_therapy + 6 months post"

alternatives:
  - {drug_id: DRUG-DAPSONE, condition: "sulfa allergy", dose: "100 mg daily"}
  - {drug_id: DRUG-ATOVAQUONE, condition: "sulfa allergy, dapsone intolerance"}
  - {drug_id: DRUG-PENTAMIDINE-INHALED, condition: "drug intolerance"}

# When indicated
triggers:
  - {regimen_contains_drug_class: "purine_analog"}
  - {regimen_id: REG-BR-LYMPHOMA}
  - {regimen_id: REG-R-CHOP}
  - {prolonged_corticosteroid_use_days: ">21"}
  - {patient_immunodeficiency: true}

# Rationale
rationale: >
  Regimens causing CD4 lymphopenia (including bendamustine-containing
  and R-CHOP) increase risk of PJP. Prophylaxis reduces incidence from
  ~5% to <1%.

source_refs: [SRC-IDSA-PJP-GUIDELINES, SRC-NCCN-SUPPORTIVE]
last_reviewed: "2026-04-15"
reviewers: [reviewer-id-id, reviewer-id-hem]
```

---

## 12. Entity: MonitoringSchedule

Schedule of tests/visits during regimen.

### 12.1. Schema

```yaml
# File: knowledge_base/monitoring/br_standard.yaml

entity_type: MonitoringSchedule
id: MON-BR-STANDARD
version: "1.0.0"

linked_to_regimen: REG-BR-LYMPHOMA

phases:
  - phase_name: "Pre-treatment"
    window: "week -2 to week 0"
    required_tests: [TEST-CBC, TEST-LFT, TEST-HCV-RNA, TEST-HBV-SEROLOGY, TEST-FIB-4, TEST-ECG]
    desired_tests: [TEST-ECHO-LVEF]
    visits: 1

  - phase_name: "Cycle 1 intensive monitoring"
    window: "weeks 0-4"
    recurring_tests:
      - {test: TEST-CBC, frequency: "weekly"}
      - {test: TEST-CMP, frequency: "weekly"}
    checkpoints:
      - {week: 4, test: TEST-HCV-RNA-QUANT}
    visits: "weekly"

  - phase_name: "Cycles 2-6"
    window: "weeks 4-24"
    recurring_tests:
      - {test: TEST-CBC, frequency: "before each cycle + day 14"}
      - {test: TEST-CMP, frequency: "before each cycle"}
    checkpoints:
      - {week: 12, test: TEST-HCV-RNA-QUANT, note: "Post-DAA completion"}
      - {after_cycle: 3, test: IMAGING-CT-OR-PET, note: "Interim response assessment"}
      - {after_cycle: 6, test: IMAGING-CT-OR-PET, note: "End-of-induction response"}

  - phase_name: "Maintenance (rituximab q8w)"
    window: "weeks 24-128"
    recurring_tests:
      - {test: TEST-CBC, frequency: "before each dose"}
      - {test: TEST-CMP, frequency: "before each dose"}
    checkpoints:
      - {week: 48, test: TEST-HCV-RNA-QUANT, note: "SVR24 confirmation"}
      - {frequency_months: 6, tests: [TEST-LIVER-US, TEST-AFP], note: "HCC screening post-HCV"}

  - phase_name: "Lifelong surveillance"
    window: "after week 128"
    recurring_tests:
      - {frequency_months: [3, 6], test: "clinical_exam"}
      - {frequency_months: [6, 12], test: IMAGING-CT, duration_years: 5}
      - {frequency_months: 6, tests: [TEST-LIVER-US, TEST-AFP], duration: "lifelong"}

source_refs: [SRC-NCCN-BCELL-V2-2026, SRC-EASL-HCV-2023]
last_reviewed: "2026-04-15"
reviewers: [reviewer-id]
```

---

## 13. Entity: Algorithm

Decision tree for two-plan generation.

### 13.1. Schema

```yaml
# File: knowledge_base/algorithms/hcv_mzl_1l_choice.yaml

entity_type: Algorithm
id: ALGO-HCV-MZL-1L-CHOICE
version: "1.0.0"

applicable_to:
  disease_id: DIS-HCV-MZL
  line_of_therapy: 1

# Output
purpose: "Select between standard and aggressive 1L regimen"
output_indications: [IND-HCV-MZL-1L-STANDARD, IND-HCV-MZL-1L-AGGRESSIVE]
default_indication: IND-HCV-MZL-1L-STANDARD

# Decision tree
decision_tree:
  - step: 1
    description: "Are there red flags AGAINST aggressive regimen?"
    evaluate:
      any_of:
        - red_flag: RF-LVEF-LOW
        - red_flag: RF-CIRRHOSIS-OR-FIB4-HIGH
        - red_flag: RF-ECOG-HIGH
        - red_flag: RF-SEVERE-NEUROPATHY
        - red_flag: RF-AMIODARONE
        - red_flag: RF-NO-ECHO-AVAILABLE
        - red_flag: RF-AGE-OVER-75
    if_true:
      result: IND-HCV-MZL-1L-STANDARD
      reason: "Contraindications to aggressive regimen"
      stop: true
    if_false:
      continue_to: 2

  - step: 2
    description: "Are there red flags FOR aggressive regimen?"
    evaluate:
      any_of:
        - red_flag: RF-B-SYMPTOMS
        - red_flag: RF-LDH-HIGH
        - red_flag: RF-RAPID-PROGRESSION
        - red_flag: RF-BULKY-DISEASE
        - red_flag: RF-HYPERCALCEMIA
        - red_flag: RF-HISTOLOGICAL-TRANSFORMATION
    if_true:
      result: IND-HCV-MZL-1L-AGGRESSIVE
      reason: "Indicators for aggressive regimen present"
    if_false:
      result: IND-HCV-MZL-1L-STANDARD
      reason: "Default recommendation (consensus)"

# Output format
always_show_both:
  description: >
    Both standard and aggressive indications are always presented to
    the clinician. Algorithm determines which is marked "default" vs
    "alternative", but both documents are generated for comparison.
  enforcement: "mandatory_two_plan_output"

source_refs: [SRC-NCCN-BCELL-V2-2026, SRC-ESMO-MZL-2020, SRC-ALDERUCCIO-2024]
last_reviewed: "2026-04-15"
reviewers: [reviewer-id-hem-1, reviewer-id-hem-2]
```

---

## 14. Entity: Source

Metadata for any source.

### 14.1. Schema

```yaml
# File: knowledge_base/sources/nccn_bcell_v2_2026.yaml

entity_type: Source
id: SRC-NCCN-BCELL-V2-2026
version: "1.0.0"

source_type: "guideline"
# guideline | phase3_rct | phase2_trial | phase1_trial |
# meta_analysis | systematic_review | regulatory |
# clinical_trial_registry | molecular_kb | monograph | review

title: "NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas"
version_or_edition: "Version 2.2026"
publisher: "National Comprehensive Cancer Network"
publication_year: 2026
publication_date: "2026-02-15"

# For articles
authors: []
journal: null
doi: null
pmid: null

# Access
url: "https://www.nccn.org/guidelines/guidelines-detail?category=1&id=1480"
access_level: "subscription_required"
# open_access | subscription_required | registered_free | limited

currency_status: "current"
# current | superseded | historical
superseded_by: null
current_as_of: "2026-04-15"

# Tier assignment per CCS §2
evidence_tier: 1

# Licensing & hosting (per SOURCE_INGESTION_SPEC §3)
hosting_mode: "referenced"          # hosted | referenced | mixed
hosting_justification: null         # H1..H5 per SOURCE_INGESTION_SPEC §1.4 (null if referenced)
ingestion:
  method: "live_api"                # live_api | scheduled_batch | manual | none
  client: null                      # module name if live_api, null otherwise
  endpoint: null
  rate_limit: null
cache_policy:
  enabled: false
  ttl_hours: null
  scope: null                       # query_result | entity_snapshot | none
license:
  name: "NCCN proprietary"
  url: "https://www.nccn.org/permissions"
  spdx_id: null                     # SPDX if applicable (e.g. "CC-BY-4.0", "CC0-1.0")
attribution:
  required: true
  text: "Reproduced with permission from the NCCN Clinical Practice Guidelines..."
  logo_url: null
commercial_use_allowed: false
redistribution_allowed: false
modifications_allowed: false
sharealike_required: false
known_restrictions:
  - "No redistribution of content; only our paraphrase + link per SOURCE_INGESTION_SPEC §1.2"
legal_review:
  status: "reviewed"                # pending | reviewed | escalated
  reviewer: null
  date: null
  notes: null

# Related
relates_to_diseases: [DIS-HCV-MZL, DIS-DLBCL, DIS-FOLLICULAR-LYMPHOMA, "..."]

notes: >
  Primary reference for all B-cell lymphoma indications. Updated
  quarterly. Check for new versions every 3 months as part of
  knowledge base hygiene (CCS §9.1).
last_verified: "2026-04-15"
verifier: [reviewer-id]
```

**Fields overlap with SOURCE_INGESTION_SPEC §3.** The two documents
describe the same thing; in case of discrepancy, SOURCE_INGESTION_SPEC
prevails as the later and more detailed specialized document.

---

## 15. Overall data model (relational view)

For developers, relational mapping:

```
DISEASE (1) ──────< (N) INDICATION >──────── (1) REGIMEN
                       │                         │
                       │                         ├──< (N) DRUG (via components)
                       │                         │
                       │                         ├── (1) MONITORING_SCHEDULE
                       │                         │
                       │                         └──< (N) SUPPORTIVE_CARE (mandatory)
                       │
                       ├──< (N) CONTRAINDICATION (hard)
                       │
                       ├──< (N) RED_FLAG (triggers alternative)
                       │
                       ├──< (N) TEST (required / desired)
                       │
                       └──< (N) SOURCE (evidence)

ALGORITHM (1) ──────< (N) INDICATION (outputs)
          └──────< (N) RED_FLAG (uses as inputs)

BIOMARKER ──── linked_via ──── INDICATION, DISEASE, DRUG
```

---

## 16. Storage options

Schema is **format-agnostic**. Three reasonable implementations:

### 16.1. YAML files in git (MVP recommended)

```
knowledge_base/
├── diseases/
│   └── hcv_mzl.yaml
├── drugs/
│   ├── rituximab.yaml
│   └── bendamustine.yaml
├── regimens/
│   ├── br.yaml
│   └── r_chop.yaml
├── indications/
│   ├── hcv_mzl_1l_standard.yaml
│   └── hcv_mzl_1l_aggressive.yaml
├── contraindications/
├── red_flags/
├── tests/
├── supportive_care/
├── monitoring/
├── algorithms/
└── sources/
```

**Advantages:**
- Git history = complete audit trail
- Standard OSS workflow (PRs, reviews)
- Clinicians can edit in a text editor
- Human-readable, human-reviewable
- No database infrastructure needed for MVP

**Disadvantages:**
- Referential integrity is not enforced automatically — a validator is needed
- Performance is limited for large KBs (thousands of entities)

### 16.2. PostgreSQL with JSON columns

For the version when the knowledge base grows:
- Core fields — typed columns
- Flexible content (trees, conditions) — JSONB
- Referential integrity via foreign keys
- Full-text search built-in

### 16.3. Graph database (Neo4j, ArangoDB)

Optimal for complex multi-hop queries (biomarker → drugs → regimens → ...).
Overkill for MVP.

**Recommendation:** start with 16.1, migrate to 16.2 when the pilot
diagnosis proves viability (scaling + production reliability).

---

## 17. Validation tooling

What the developer must build from day one:

**Entity validator:**
- Verifies that all required fields are populated
- Verifies that all `_id` references are valid (no dangling references)
- Verifies that `version` is semantic and increases
- Verifies that `last_reviewed` is not older than the threshold

**Source checker:**
- Verifies that all sources exist in `sources/`
- Verifies that URLs are accessible (periodic check)
- Verifies that `currency_status` is not `superseded` without `superseded_by`

**Clinical review enforcer:**
- Verifies that each Indication has >= 2 reviewers
- Verifies that reviewers are from the approved list
- Blocks merge without approval from the required number

**CI/CD pipeline:**
```yaml
# .github/workflows/knowledge_validation.yml
on: pull_request
jobs:
  validate:
    steps:
      - validate_entity_schemas
      - check_referential_integrity
      - verify_source_availability
      - check_review_requirements
      - run_clinical_tests  # sample patient cohort
```

---

## 18. Governance of this document

- Schema changes require consensus from all Clinical Co-Leads + Tech Lead
- 14-day public comment period before a major version
- Breaking changes (renaming fields, changing types) — major version bump
- Changelog in CHANGELOG-SCHEMA.md

---

## 19. Current status and limitations

**v0.1 means:**
- Skeleton for the first enrollment — HCV-MZL
- Requires refactoring after the first real implementation
- Not validated against other diagnoses

**Known limitations:**
- Not modeled: clinical trial matching (requires a separate entity), ~~genetic syndromes (such as germline BRCA)~~ — *germline-syndrome modeling addressed for the prevention persona by §20 (ratified 2026-05-18); treatment-time germline integration still pending* — multidisciplinary coordination
- Fine-grained dose modifications — simplified
- Temporal reasoning (what happens when) — limited
- Interaction with patient preferences — not yet modeled

**What needs to be done after v0.1:**
- Implement HCV-MZL in full according to this schema
- Compare generated output against the reference document
- Iterate based on gaps

---

**Pull requests on the Schema are welcomed, but must go through CHARTER §6 governance.**


---

## 17. Solid-tumor extensions (RATIFIED 2026-05-07)

**Status:** ratified 2026-05-07. Drives 5 GI diagnoses (CRC, gastric/GEJ,
PDAC, HCC, esophageal). Schema-side ratification landed in
`feat/schema-17-refactor-2026-05-07-2200` (Pydantic models, loader
ref-integrity, golden fixtures, 5 GI disease re-stamps). Engine
pass-through and render phased-timeline are deferred to Phase C readiness
work in the GI-2 wave (planning doc
`docs/plans/schema_17_refactor_2026-05-07.md` §2.7).

**Original status (2026-04-26):** open. Each of the 5 GI diseases was
committed initially as `proposal_status: partial` until the proposal
resolved; ratification re-stamped them to `full` and removed the
`awaiting_proposal` marker.

**Why now:** OpenOnco v0.1 was built around hematolymphoid diseases where
1L = "pick a chemo regimen + monitoring". Solid tumors introduce three
patterns the schema does not represent today:

1. **Sequential phases inside one line of therapy.** Periop FLOT
   (gastric) = neoadjuvant chemo cycles 1–4 → surgery → adjuvant chemo
   cycles 5–8. CROSS (esophageal) = neoadjuvant CRT → esophagectomy →
   optional adjuvant ICI. Today `Indication.followed_by` means "next
   line", not "next phase of this 1L bundle"; engine and render layers
   don't model intra-line ordering.

2. **Surgery as a treatment modality.** Whipple (PDAC), low-anterior
   resection (rectum), gastrectomy (gastric), esophagectomy, hepatic
   resection / transplant (HCC) are first-line treatments. Today there
   is no Surgery entity. Treating surgery as a `Drug` is wrong; treating
   it as a free-text note loses the resectability gate, MDT-trigger, and
   complication linkage.

3. **Radiation therapy as concurrent / sequential treatment.** CROSS =
   41.4 Gy in 23 fractions concurrent with carbo-paclitaxel; rectal SCRT
   = 25 Gy / 5 fx; HCC SBRT; definitive CRT for esophageal squamous
   unresectable. RT dose / fractionation / target volume / OARs / total
   BED have no representation. Concurrent chemo-RT is doubly
   unmodellable today.

### 17.1. Ratified entities

```yaml
# entity_type: Surgery
id: SUR-WHIPPLE
names: {preferred: "Pancreaticoduodenectomy (Whipple)"}
type: pancreaticoduodenectomy
intent: curative  # | palliative | diagnostic | salvage
target_organ: pancreas_head
applicable_diseases: [DIS-PDAC]
operative_mortality_pct: "1-3% in high-volume centers"
common_complications:
  - {name: "POPF (pancreatic fistula)", frequency: "10-20%"}
  - {name: "Delayed gastric emptying", frequency: "15-25%"}
sources: [SRC-NCCN-PANCREATIC-2025, SRC-ESMO-PANCREATIC-2024]

# entity_type: RadiationCourse
id: RT-CROSS-NEOADJ
names: {preferred: "CROSS neoadjuvant CRT"}
total_dose_gy: 41.4
fractions: 23
fraction_size_gy: 1.8
target_volume: "primary + involved nodes (CTV)"
schedule: "5 fx/week × 4.6 weeks"
concurrent_chemo_regimen: REG-CARBOPLATIN-PACLITAXEL-WEEKLY  # optional ID
intent: neoadjuvant  # | definitive | adjuvant | palliative
sources: [SRC-CROSS-2012, SRC-NCCN-ESOPHAGEAL-2025]

# Indication addition (extends §7 schema)
applicable_to:
  ...existing fields...
phases:                       # NEW — ordered list within ONE indication
  - phase: neoadjuvant
    type: chemotherapy        # | surgery | radiation | chemoradiation
    regimen_id: REG-FLOT
    cycles: 4
  - phase: surgery
    type: surgery
    surgery_id: SUR-TOTAL-GASTRECTOMY
  - phase: adjuvant
    type: chemotherapy
    regimen_id: REG-FLOT
    cycles: 4
```

### 17.2. Engine + render impact

- `engine.algorithm_eval` already returns one Indication per
  algorithm; with `phases:` populated, render layer must walk the
  ordered list and emit a phased timeline (current `_render_timeline`
  composes induction → response → maintenance from regimen + monitoring;
  `phases:` is an explicit override).
- Surgery and RadiationCourse become first-class entity types in
  `validation/loader.py`. New referential-integrity checks: every
  `phases[*].surgery_id` resolves to a Surgery; every `radiation_id`
  resolves to a RadiationCourse.
- Fixture-level testing: golden fixtures exercise the phased-output
  contract per disease.

### 17.3. Interim handling (the diseases shipped in this commit)

Until the proposal is ratified by clinical co-leads and engine work
lands:

- All 5 GI diseases are committed with `archetype: stage_driven` (HCC
  also keeps `etiological_factors` populated — see §3.3 — but its
  primary archetype is `stage_driven` via BCLC).
- Indications use only the existing `applicable_to.stage_requirements`
  + `recommended_regimen` + `concurrent_therapy` + `followed_by` slots.
  Where periop sequencing is clinically essential (FLOT, CROSS, mFOLFIRINOX
  adjuvant), the regimen entry is the "main pharma cycle" and the
  surgical / RT step is described in `Indication.notes` as free text.
  This is **lossy** — the engine cannot enforce "did surgery happen
  before adjuvant?" — and is the explicit reason the diseases are marked
  `partial`.
- Each affected disease YAML carries:
  ```yaml
  metadata:
    proposal_status: partial
    awaiting_proposal: "KNOWLEDGE_SCHEMA_SPECIFICATION.md §17 Solid-tumor extensions"
  ```

### 17.4. Resolution path

1. Clinical co-leads review §17.1 and either ratify or counter-propose.
   **Done 2026-05-07** (dev-mode autonomous per CHARTER §6.1 v0.1
   exemption — `project_charter_dev_mode_exemptions.md`).
2. **Done 2026-05-07.** Pydantic schemas added: `surgery.py`,
   `radiation_course.py`, `Indication.phases: list[IndicationPhase] | None`.
   `IndicationPhase` lives in `indication.py` (matches `RegimenPhase`'s
   sibling-in-same-file pattern in `regimen.py`). Phase-stage enum extends
   §17.1 (neoadjuvant / surgery / adjuvant) with induction / maintenance /
   definitive; phase-type enum extends with targeted_therapy / immunotherapy.
3. **Done 2026-05-07.** Loader-side referential integrity for
   `phases[*].surgery_id` → Surgery, `phases[*].radiation_id` →
   RadiationCourse, `phases[*].regimen_id` → Regimen,
   `Surgery.applicable_diseases[]` → Disease,
   `RadiationCourse.concurrent_chemo_regimen` → Regimen.
4. Engine: pass-through of `phases` into `PlanTrack.indication_data`.
   **Deferred to Phase C** of the GI-2 wave (1-line change paired with
   the first phased indication that lands).
5. Render: phased-timeline section. **Deferred to Phase C** —
   `_render_timeline` extension lands with the first periop FLOT / CROSS
   indication that needs to render.
6. Tests: golden fixtures per disease that assert the phased output.
   **Schema-level done 2026-05-07** (`tests/fixtures/phased_indication.yaml`,
   `surgery_whipple.yaml`, `radiation_cross.yaml`); per-disease engine /
   render fixtures land alongside steps 4-5 in Phase C.
7. **Done 2026-05-07.** Re-stamped 5 GI diseases as
   `proposal_status: full` and removed the `awaiting_proposal` field.

---

## 20. Prevention extensions (RATIFIED 2026-05-18)

**Status:** ratified 2026-05-18 under CHARTER §12 dev-mode exemption
(Initiator-only, v0.1 phase). Drives the prevention / early-diagnosis
deliverable scoped by CHARTER §3 (amended 2026-05-18) and proposed in
`docs/plans/openonco_prevention_scope_2026-05-18-1500.md` (Path A —
HCP-mediated). Engine, validator, and render passes are deferred to the
v0.2 implementation waves; this section ratifies only the schema-level
contract.

**Why now:** CHARTER §3 was amended on 2026-05-18 to include
HCP-mediated prevention / early-diagnosis recommendations for at-risk
asymptomatic individuals. The existing schema can compose most of the
required pattern (`Disease.archetype = etiologically_driven` already
covers infectious causation; `RedFlag` already drives Indication routing;
`Algorithm` already encodes decision trees), but four fields are missing
to disambiguate prevention output from treatment output and to mark
biomarkers usable in asymptomatic patients. This section adds those
four fields without introducing any new top-level entity.

### 20.1. Ratified additive fields

```yaml
# Indication addition (extends §7 schema)
intent: treatment        # NEW enum, default = "treatment" (on read; no
                         # backfill required across existing ~400 YAMLs).
                         # Valid values:
                         #   treatment    — current implicit behaviour
                         #   prevention   — for at-risk asymptomatic individuals
                         #   screening    — population/risk-group screening cadence
                         #   surveillance — known carriers / post-treatment monitoring

# Biomarker additions (extend §4 schema)
clinical_context:        # NEW array enum, multi-valued. Default on read:
                         # ["tumor_profiling"] (current implicit behaviour).
                         # Valid values:
                         #   germline_susceptibility  — hereditary risk variants (BRCA1/2, VHL, FH, MMR, ...)
                         #   tumor_profiling          — current implicit (HER2, KRAS, ...)
                         #   screening_surveillance   — used for asymptomatic monitoring in high-risk subgroups
                         #                              (AFP in cirrhosis, calcitonin in MEN2, ...)
                         #   prognostic               — affects prognosis of known disease
                         #   predictive               — predicts response to a specific therapy
                         # One marker MAY carry multiple contexts (e.g., MMR/MSI =
                         # germline_susceptibility + tumor_profiling + predictive).
  - tumor_profiling

applicable_in_asymptomatic: false   # NEW bool, default false. Fast filter for
                                    # prevention-plan composition; only true for
                                    # markers with established asymptomatic use
                                    # (germline panels, syndrome-specific monitoring
                                    # markers).

# RedFlag addition (extends §9 schema)
risk_category:           # NEW enum, optional (current treatment-time RedFlag
                         # categories continue to work without this field).
                         # Valid values (prevention persona):
                         #   genetic            — pedigree-driven, germline-test indication
                         #   infectious         — chronic infection that elevates cancer risk
                         #   chronic_condition  — autoimmune / inflammatory / metabolic precondition
                         #   occupational       — IARC-classified workplace exposure
                         #   iatrogenic         — prior radiation / immunosuppression / cytotoxic Rx
                         #   lifestyle          — smoking, alcohol, BMI, diet, UV
                         #   reproductive       — parity, menarche/menopause, HRT
```

### 20.2. Engine + render impact (deferred to v0.2 implementation waves)

- `engine.plan` introduces a `PreventionPlan` output shape parallel to
  the existing `Plan`. Same `tracks` architecture (≥2 tracks per
  CHARTER §15.2 C4 — e.g., standard-surveillance vs. intensified-
  surveillance, or treat-the-cause vs. monitor).
- The Plan-vs-PreventionPlan branch is selected on patient input:
  - patient carries a confirmed Disease → Plan (treatment, existing).
  - patient carries no confirmed Disease but ≥1 prevention-eligible
    RedFlag (genetic / infectious / occupational / ...) → PreventionPlan.
- Engine filters `Indication` entities by `intent`: Plan uses
  `intent = treatment` (or unset → defaults to treatment); PreventionPlan
  uses `intent ∈ {prevention, screening, surveillance}`.
- Engine filters `Biomarker` entities for the asymptomatic case by
  `applicable_in_asymptomatic = true` AND `clinical_context` ∋
  `{germline_susceptibility, screening_surveillance}`.
- Render: PreventionPlan reuses the existing clinician + patient-mode
  render contracts (PATIENT_MODE_SPEC). The patient bundle remains a
  translation, not a separate clinical product — preserving the §15 C1
  HCP-only positioning.
- Validator: existing referential-integrity rules apply unchanged. New
  enum constraints on `Indication.intent`, `Biomarker.clinical_context`,
  `RedFlag.risk_category` are loader-level Pydantic validation.

### 20.3. Pilot sequence (deferred to v0.2 chunk specs)

Per the originating scope proposal:

- **v0.2-A: Infectious etiologies** (recommended starter). HepB, HepC,
  HPV, H. pylori, EBV, HIV, HTLV-1 as `Indication(intent=prevention)`
  cases. Highest ROI in Ukraine; validated by patient-zero (HCV-MZL DAA
  pathway); cleanest source-license posture (IARC Group 1 public, WHO,
  AASLD/NCCN already in KB).
- **v0.2-B: Hereditary risk** (germline + pedigree triage). Multi-syndrome
  (BRCA/HBOC, Lynch, Li-Fraumeni, FAP/MAP, hereditary RCC syndromes
  VHL/HLRCC/BHD/HPRC/BAP1). Lynch pilots the architecture first. Risk
  models (Amsterdam II, PREMM5, Manchester, Tyrer-Cuzick v8, BOADICEA)
  encoded as declarative `Algorithm` entities re-implemented from
  published primary papers. NCCN Genetic/Familial High-Risk license
  posture must be verified before relying on it (open question #7 in
  the scope proposal).
- **v0.3: Occupational + chronic conditions** (IARC Group 1 environmental
  + inflammatory predispositions like Barrett's, IBD, PSC, celiac).
- **v0.3+: Lifestyle, iatrogenic, reproductive** (full 7-category
  coverage).

### 20.4. Resolution path

1. Clinical Co-Leads review §20.1 and either ratify or counter-propose.
   **Ratified 2026-05-18** under CHARTER §12 dev-mode exemption
   (Initiator-only, v0.1 phase). Formal Co-Lead ratification queued for
   first-Co-Lead appointment.
2. Pydantic schema additions: `Indication.intent: Literal[...] = "treatment"`,
   `Biomarker.clinical_context: list[Literal[...]] = ["tumor_profiling"]`,
   `Biomarker.applicable_in_asymptomatic: bool = False`,
   `RedFlag.risk_category: Optional[Literal[...]] = None`. **Pending v0.2
   implementation.**
3. Loader-side enum validation. **Pending v0.2 implementation.**
4. Engine: `PreventionPlan` shape + intent-filtering branch in
   `plan.generate_plan()`. **Pending v0.2 implementation.**
5. Render: PreventionPlan render contract (likely reuses `_render_plan`
   with intent-aware section labels). **Pending v0.2 implementation.**
6. Tests: golden fixtures for the first v0.2-A infectious-etiology case
   (HCV-MZL prevention pathway is the natural anchor — it inverts the
   existing patient-zero treatment fixture). **Pending v0.2-A chunk.**

### 20.5. Banned sources reminder

Per CHARTER §2 and project policy, the following sources remain banned
for the OpenOnco pilot and must not appear in any prevention-side
sources/citations: **OncoKB** (ToS conflict with CHARTER §2 free public
resource), **SNOMED CT** (license), **MedDRA** (license). Substitutes
for the prevention domain: IARC Monographs (public), WHO, USPSTF (public
domain), AASLD, NCCN (existing license; Genetic/Familial sub-license to
be verified before use), ESMO, peer-reviewed primary publications.
