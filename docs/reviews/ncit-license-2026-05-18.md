# NCI Thesaurus license review — 2026-05-18

Per `specs/SOURCE_INGESTION_SPEC.md` §8 and §20. Classifies the NCI
Thesaurus (NCIt) for OpenOnco reuse as the term-normalization layer
behind `BIO-*` / `DIS-*` entity IDs.

## TL;DR

- **License class:** US Public Domain (17 U.S.C. §105 — federal-government works).
- **Hosting mode:** `referenced` (default per `SOURCE_INGESTION_SPEC §1.4`).
- **Four constraints clear:** commercial ✓, redistribution ✓, modifications ✓, share-alike NOT required.
- **Attribution:** not required; courtesy text published in `src_ncit.yaml.attribution.text`.
- **One scope boundary:** NCIt cross-references concepts to other vocabularies (SNOMED CT, MedDRA, ICD-O-3, MeSH). Cross-reference *codes* are NOT NCI-authored content — those code systems retain their own licenses. OpenOnco only consumes the NCIt concept layer.
- **`legal_review.status: reviewed`** in `src_ncit.yaml`. Re-review triggers documented below.

## What NCIt is

The NCI Thesaurus is the National Cancer Institute's reference vocabulary
for cancer concepts. Maintained by the NCI Enterprise Vocabulary Services
(EVS), it covers:

- Diseases (e.g. C2926 = Non-Small Cell Lung Carcinoma)
- Biomarkers / genes / variants (e.g. C17068 = EGFR Gene, C20188 = EGFR Mutation)
- Drugs and active agents
- Anatomic sites
- Procedures and interventions
- Pathologic findings

Each concept carries a stable NCIt code, a preferred term, alternate
synonyms, NCI-authored definitions, and machine-readable cross-references
to other vocabularies (SNOMED CT, MedDRA, ICD-O-3, MeSH, etc.).

Public-facing surfaces:
- Browser: <https://ncithesaurus.nci.nih.gov/ncitbrowser/>
- EVS REST API: <https://api-evsrest.nci.nih.gov/api/v1/>
- Documentation: <https://api-evsrest.nci.nih.gov/swagger-ui.html>

## Why we want it

The OpenOnco patient-input flow accepts free-text disease and biomarker
mentions ("lung cancer", "EGFR positive"). These need to resolve to KB
IDs (`DIS-NSCLC`, `BIO-EGFR-MUTATION`) so the engine can route.

Today's normalization is ad-hoc: each `Disease` / `Biomarker` entity
carries its own `names: {en, ua}` block, plus a small `alternate_names`
list, and the matching layer compares free text against those. That
scales poorly:

- Multi-language matching is brittle (Ukrainian + English only)
- Synonyms drift between entities
- New free-text input that wasn't anticipated by the entity author silently misses

NCIt gives us a canonical mapping layer:

1. Patient enters "lung cancer" → NCIt search returns C2926 (NSCLC) +
   neighbours (C3262 Lung Carcinoma, C3905 Small Cell Lung Carcinoma, …)
2. Each KB Disease has `codes.ncit` populated (`DIS-NSCLC.codes.ncit = "C2926"`)
3. The matching layer resolves free text → NCIt code → KB ID

Same pattern for biomarkers. NCIt's synonym tables (NCI maintains them
centrally) eliminate the per-entity-author-rolls-their-own problem.

## License classification

### Primary basis: 17 U.S.C. §105

> "Copyright protection under this title is not available for any work
> of the United States Government …"

NCI EVS is a unit of the National Institutes of Health, a US federal
agency. NCIt content is authored by federal employees acting in their
official capacity. It is therefore ineligible for US copyright
protection and is in the **public domain within the United States**.

### NCI's own statement

The cancer.gov reuse policy at <https://www.cancer.gov/policies/copyright-reuse>
states:

> "Most of the text on this website is freely available for reuse —
> except for material we have explicitly noted as borrowed from
> external sources. Cancer information is generally NOT copyrighted
> and there are usually no restrictions on its use."

Same posture used for SRC-PDQ (PR #589) and SRC-CTGOV-REGISTRY (PR #592).

### Four-constraint check (per `SOURCE_INGESTION_SPEC §8`)

| Constraint | Answer | Source |
| --- | --- | --- |
| Commercial use allowed? | **Yes** | 17 U.S.C. §105; NCI policy |
| Redistribution allowed? | **Yes** | Same |
| Modifications allowed? | **Yes** | Same — public-domain text is freely modifiable |
| ShareAlike required? | **No** | Public-domain works carry no downstream license obligation |

### Cross-reference scope boundary

NCIt records carry cross-references to other vocabularies. For example,
the NCIt record for "Non-Small Cell Lung Carcinoma" includes the
matching SNOMED CT code (254637007) and ICD-10 code (C34.9).

**The cross-reference *codes themselves* are NOT NCI-authored content.**
The license posture of each external vocabulary applies:

- **SNOMED CT codes** — IHTSDO license, country affiliate fees apply.
  Excluded from MVP per `CLAUDE.md` ("No SNOMED CT, no MedDRA in MVP — license gates").
- **MedDRA codes** — paid commercial license required. Excluded similarly.
- **ICD-10 / ICD-O-3 codes** — WHO maintains; permissive for most uses.
- **MeSH codes** — NLM, public domain.

OpenOnco's use of NCIt is **only the NCIt concept code layer**:
`{code: "C2926", name: "Non-Small Cell Lung Carcinoma", synonyms: [...]}`.
We do NOT consume the cross-referenced SNOMED CT / MedDRA codes. The
EVS API can be queried with `include=summary` to get exactly this
narrow projection — synonyms + definition, no cross-refs. This is the
default in `ncit_client.NcitQuery.include`.

If a future workstream needs richer cross-references, that workstream
must re-evaluate license posture for each external code system before
consuming.

## Hosting mode

`referenced`, per `SOURCE_INGESTION_SPEC §1.4` default. We do not host
NCIt content in the repo; we store NCIt codes (e.g. "C2926") on
`Disease.codes.ncit` and `BiomarkerExternalIDs.ncit`, and resolve them
to display text via live API calls (with 30-day cache).

If a future workstream needs offline normalization (e.g. for a
fully-offline Pyodide bundle), migrating to `hosted` mode requires
fresh review covering snapshot cadence (NCIt updates monthly),
attribution boilerplate (already drafted), and storage scale.

For now: referenced.

## Engineering scope (this PR)

1. `knowledge_base/clients/ncit_client.py` — `BaseSourceClient` subclass.
   Two query modes: `get_concept` (by NCIt code) and `search` (by
   free-text term). Live calls gated behind `OPENONCO_NCIT_LIVE=1`.
   `include=summary` default keeps responses narrow (no cross-ref codes).
2. `knowledge_base/hosted/content/sources/src_ncit.yaml` — Source entity
   with full license metadata, hosting=referenced, attribution-required=false,
   `legal_review.status: reviewed`. Cross-reference scope boundary
   recorded under `known_restrictions`.
3. `knowledge_base/schemas/disease.py` — `DiseaseCodes.ncit: Optional[str]`.
4. `knowledge_base/schemas/biomarker.py` — `BiomarkerExternalIDs.ncit: Optional[str]`.
5. `tests/test_ncit_client.py` — 14 offline tests covering gate semantics,
   HTTP-seam stubbing, query parameters, URL encoding, schema field
   round-trips, source-id drift guard.
6. `tests/fixtures/ncit_responses/` — 2 stub JSON files derived from
   the EVS public schema (no NCIt content reproduced beyond canonical
   codes already in our memory like C2926, C17068, C20188).

## NOT in scope (deliberately)

- **No per-Disease / per-Biomarker code population.** Populating `ncit`
  on each `Disease` / `Biomarker` YAML is a separate clinical-content
  workstream gated by `CHARTER §6.1` (two Clinical Co-Lead signoffs
  per authored mapping).
- **No live API calls by default.** `OPENONCO_NCIT_LIVE` must be set
  explicitly.
- **No SNOMED CT / MedDRA cross-references** consumed.
- **No `hosted` mode migration.**
- **No CI cron** for scheduled re-fetch.
- **No actual term-normalization layer** in the engine yet — that's a
  follow-up that consumes `Disease.codes.ncit` and the EVS search
  endpoint.

## Re-review triggers

Update this doc and flip `legal_review.status` if any of:

1. NCI changes its `cancer.gov/policies/copyright-reuse` page.
2. OpenOnco changes its `CHARTER §2` posture (any paid tier).
3. We start consuming cross-referenced **SNOMED CT** or **MedDRA**
   codes from NCIt records — would inherit those vocabularies' license
   constraints; both are explicitly excluded from MVP per `CLAUDE.md`.
4. We adopt `hosted` mode (snapshotting NCIt content into the repo).
5. EVS API changes its terms of service.

## Sign-off

- **Reviewer:** claude (self-review under `CHARTER §6.1` dev-mode
  exemption, v0.1 phase, per memory `project_charter_dev_mode_exemptions.md`).
- **Date:** 2026-05-18.
- **Notes:** Third "US Public Domain" source after PDQ and CTGOV.
  The novel constraint here is the cross-reference scope boundary —
  documented under `src_ncit.yaml.known_restrictions` and enforced
  by `NcitQuery.include` defaulting to `summary` rather than `full`.
