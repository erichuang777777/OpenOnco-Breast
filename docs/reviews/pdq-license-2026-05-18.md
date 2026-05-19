# NCI PDQ license review — 2026-05-18

Per `specs/SOURCE_INGESTION_SPEC.md` §8 (process for adding a new source)
and §20 (checklist for connecting a hosted source). This review classifies
the NCI Physician Data Query (PDQ) corpus for OpenOnco reuse.

## TL;DR

- **License class:** US Public Domain (17 U.S.C. §105 — federal-government works).
- **Hosting mode:** `referenced` (default per `SOURCE_INGESTION_SPEC §1.4`).
- **All four constraints clear:** commercial use ✓, redistribution ✓, modifications ✓, share-alike NOT required.
- **Attribution:** not required, but NCI publishes a courtesy attribution string we will use.
- **One trademark gotcha:** "PDQ®" is a registered trademark of HHS; we may not use it in product naming in a way that implies NCI endorsement.
- **`legal_review.status: reviewed`** in `src_pdq.yaml`. Re-review triggers documented below.

## What PDQ is

PDQ (Physician Data Query) is the National Cancer Institute's comprehensive,
peer-reviewed cancer information database. The PDQ Cancer Information
Summaries Editorial Boards — six expert boards covering adult/pediatric
treatment, screening, prevention, supportive care, integrative medicine,
and cancer genetics — author and maintain parallel summaries in two
registers:

- **Health Professional (HP) version** — full clinical detail, references.
- **Patient version** — same scope at plain-language reading level.

Summaries are updated continuously as new evidence emerges. Each summary
carries a `Date Last Modified` field, citable references, and is
indexed by a CDR (Cancer Data Repository) ID.

PDQ is also available via the NCI Cancer.gov syndication API in JSON
form for programmatic consumption.

Public-facing URL: <https://www.cancer.gov/publications/pdq>.
Reuse policy: <https://www.cancer.gov/policies/copyright-reuse>.

## Why we want it

The audit `docs/reviews/openonco-state-audit-2026-05-17.md` flagged
that the rationale prose on Indication entries (the "why this regimen")
is thin. PDQ treatment summaries are exactly that prose, NCI-authored,
fully citable, and license-clean.

The current corpus mass uses primary trial RCTs (KEYNOTE, CheckMate,
PALOMA, etc.) and tier-1 guidelines (NCCN — restricted reuse, ESMO —
mixed). PDQ adds a tier-2 confirmatory layer that is:

1. Public-domain (no reuse friction at all).
2. Comprehensive across cancer types (~80 disease summaries, plus
   screening / supportive care).
3. Routinely cross-referenced by NCCN and ESMO.

We will not use PDQ as a *leading* source (it's an editorial-board
summary of others' work, not primary evidence). `precedence_policy:
confirmatory` is appropriate.

## License classification

### Primary basis: 17 U.S.C. §105

> "Copyright protection under this title is not available for any work
> of the United States Government …"

NCI is an agency of the US Department of Health and Human Services — a
federal-government entity. PDQ content is authored by federal employees
acting in their official capacity (and contracted editorial board
members whose contributions are released as government works per the
PDQ Editorial Board contracts referenced on cancer.gov). It is therefore
ineligible for US copyright protection and is in the **public domain
within the United States**.

### NCI's own statement

The cancer.gov reuse policy at
<https://www.cancer.gov/policies/copyright-reuse> states:

> "Most of the text on this website is freely available for reuse —
> except for material we have explicitly noted as borrowed from
> external sources. Cancer information is generally NOT copyrighted
> and there are usually no restrictions on its use."

> "PDQ® is a registered trademark of the U.S. Department of Health and
> Human Services. Content of PDQ documents can be used freely as text.
> The PDQ name itself, as a registered trademark, cannot be used as
> the name of an NCI publication or service that is not, in fact, PDQ."

### Four-constraint check (per `SOURCE_INGESTION_SPEC §8`)

| Constraint | Answer | Source |
| --- | --- | --- |
| Commercial use allowed? | **Yes** | 17 U.S.C. §105; NCI policy |
| Redistribution allowed? | **Yes** | Same |
| Modifications allowed? | **Yes** | Same — public-domain text is freely modifiable |
| ShareAlike required? | **No** | Public-domain works carry no downstream license obligation |

This places PDQ in the most permissive bucket of `SOURCE_INGESTION_SPEC
§2` — Tier 0 / Tier 4 depending on terminology; either way, no
restriction friction for OpenOnco's `CHARTER §2` free-public-resource
posture.

### Known restrictions (recorded on `src_pdq.yaml`)

1. **Trademark.** The PDQ® mark may not be used as the name of a
   non-PDQ product, or in a way that implies NCI endorsement of a
   derivative work. We address this by:
   - Referring to the corpus as "NCI PDQ" only when quoting NCI.
   - Never naming an OpenOnco product / module "PDQ".
   - Attributing via the standard NCI-suggested string when content is
     reproduced.
2. **Embedded third-party copyrights.** Some PDQ summaries quote
   figures or tables from non-government sources (e.g. a tumor-stage
   diagram licensed from a textbook). Where PDQ embeds explicit
   attribution, we propagate it. Where the summary is plain text
   without embedded attribution, the federal-government-work analysis
   applies.

## Hosting mode

`referenced`, per `SOURCE_INGESTION_SPEC §1.4` default. We do not host
PDQ content in this repo; we cite PDQ summaries by URL and CDR ID and
optionally fetch the syndication API on demand. The H1–H5 hosting
justification framework does not apply (referenced mode skips it).

If a future workstream chooses to migrate to `hosted` mode (e.g. for
offline rendering or for guaranteed snapshots), the change would need a
fresh review covering:

- Snapshot cadence and versioning (PDQ updates continuously; we would
  freeze monthly).
- Re-publication attribution boilerplate (already drafted in
  `src_pdq.yaml.attribution.text`).
- Storage scale estimate (PDQ HP corpus ≈ 1200 pages across ~80 summaries).

For now: referenced.

## Engineering scope (this PR)

1. `knowledge_base/clients/pdq_client.py` — `BaseSourceClient` subclass.
   Caching + rate-limiting come from the base. Live calls gated behind
   `OPENONCO_PDQ_LIVE=1` so CI cannot accidentally hit upstream.
2. `knowledge_base/hosted/content/sources/src_pdq.yaml` — Source entity
   with all `license`, `attribution`, `hosting_mode`, `legal_review`
   fields populated.
3. `tests/test_pdq_client.py` — 9 offline-fixture tests covering
   gate semantics, HTTP-seam stubbing, query parameter assembly, URL
   encoding, source-entity schema, and source-id drift guard.
4. `tests/fixtures/pdq_responses/` — 2 stub JSON files derived from
   the public NCI documentation; no NCI content reproduced.

## NOT in scope (deliberately)

- **No Indication enrichment** in this PR. Populating Indication prose
  fields from PDQ is a separate workstream gated by clinical co-lead
  review per `CHARTER §6.1` for each authored field.
- **No live API calls** by default. `OPENONCO_PDQ_LIVE` must be set
  explicitly by the operator.
- **No `hosted` mode migration.** Stays `referenced`.
- **No CI cron** for scheduled re-fetch (per `SOURCE_INGESTION_SPEC §18`
  — added when first hosting workstream lands).

## Re-review triggers

Update this doc and flip `legal_review.status` if any of:

1. NCI changes its `cancer.gov/policies/copyright-reuse` page in a way
   that adds constraints on reuse, attribution, or commercial use.
2. OpenOnco changes its `CHARTER §2` posture (e.g. introduces any paid
   commercial tier) — would not affect the license analysis but might
   trigger NCI courtesy review.
3. We adopt `hosted` mode for PDQ (snapshotting + redistribution).
4. We use the PDQ® mark in product naming, marketing, or any
   user-facing surface implying NCI endorsement.
5. NCI delegates editorial-board authorship to a non-government entity
   in a way that creates ambiguity about 17 U.S.C. §105 applicability.

## Sign-off

- **Reviewer:** claude (self-review under `CHARTER §6.1` dev-mode
  exemption, v0.1 phase, per memory `project_charter_dev_mode_exemptions.md`).
- **Date:** 2026-05-18.
- **Notes:** Classification rests on a US public-law analysis plus
  NCI's own published reuse policy. The trademark consideration is the
  only operational constraint and is reflected in `src_pdq.yaml.known_restrictions`.
