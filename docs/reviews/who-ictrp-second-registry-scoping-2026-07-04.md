# Second trial-registry source (WHO ICTRP / EUCTR) — scoping, 2026-07-04

Per `specs/SOURCE_INGESTION_SPEC.md` §8 (process for adding a new source).
Requested as follow-up work item 5 from
`docs/reviews/ctgov-wiring-audit-2026-05-18.md`'s Gap analysis: ctgov is
currently the *only* trial-registry source, so a Ukrainian patient's
experimental-options track never surfaces EU/CTIS trials or trials
registered only in a non-US national registry.

**Pure scoping — no code, no Source entity, no client.** This session had
no network access to `who.int`, `clinicaltrialsregister.eu`, or any other
candidate registry (outbound HTTPS to both was rejected by the environment's
proxy: `CONNECT tunnel failed, response 403`). Per `specs/SOURCE_INGESTION_SPEC.md`
§8 step 1 ("Identify the license. URL to the official terms.") and per
`CLAUDE.md` ("License classification is a gate, not a formality"), that
step cannot be completed without actually reading the current terms —
guessing or reconstructing them from training-data memory would be exactly
the kind of unverified legal claim the gate exists to prevent. Unlike the
`SRC-CTGOV-REGISTRY` and `SRC-PDQ` reviews (both US-federal-government
public-domain sources, a well-established and low-ambiguity legal
category), a multi-national trial-registry aggregator's terms are not the
kind of thing safe to reason about from memory alone.

## What's being proposed and why

Two realistic candidates, both already named (but not built) in
`SOURCE_INGESTION_SPEC.md` §2.4:

| Candidate | Current spec status | Why it matters for OpenOnco |
|---|---|---|
| **WHO ICTRP** (International Clinical Trials Registry Platform) | Not in the §2.4 table at all | Meta-search aggregator over ~17 national/regional primary registries (EUCTR, CTRI/India, ANZCTR, ChiCTR, DRKS/Germany, JPRN/Japan, PACTR/Africa, and others) — the single broadest net for trials that never register with ClinicalTrials.gov |
| **EUCTR** (EU Clinical Trials Register) | Already listed, `referenced`, flagged "No friendly API, live query via scraping only on demand" | Direct source for EU-sponsored trials with Eastern-European sites — high relevance to CHARTER §1's UA-local focus, since a trial recruiting in Poland/Romania/Bulgaria is often a realistic referral target for a Ukrainian patient |

**Recommendation for a future session with network access: start with WHO
ICTRP, not EUCTR directly.** ICTRP already re-publishes EUCTR (and the
other 16 registries) under its own aggregated metadata feed, so one
client covers EUCTR's data plus everything else in one pass — versus
EUCTR alone, which the spec already flags as scrape-only and EU-specific.
This should be confirmed, not assumed — see open questions below.

## Why this is a bigger lift than `SRC-CTGOV-REGISTRY` was

The `src_ctgov.yaml` review (`docs/reviews/ctgov-wiring-audit-2026-05-18.md`
companion) took about an hour because ClinicalTrials.gov has one
unambiguous legal posture (17 U.S.C. §105, single federal agency) and an
already-integrated, already-tested client. WHO ICTRP is structurally
different on both axes:

1. **Layered licensing.** ICTRP aggregates records *from* 17+ primary
   registries, each potentially under its own terms. WHO's own re-use
   policy for the aggregated metadata may be permissive while a specific
   constituent registry's underlying record carries different terms —
   the same "curatorial layer vs. embedded third-party content" split
   `src_ctgov.yaml` already documents for individual trial sponsors,
   but one level deeper and multiplied across registries.
2. **No client exists yet.** Ctgov had `ctgov_client.py` already built,
   tested, and wired into `experimental_options.py` before its Source
   entity even existed — the audit was pure paperwork. A WHO ICTRP client
   is a from-scratch build: unknown response shape, unknown rate limits,
   unknown whether a REST API exists at all versus a bulk CSV/XML export
   (ICTRP has historically published a weekly bulk export file rather than
   a live query API — this needs verification, not assumption).
3. **Real legal review needs eyes on the actual current Terms of Use
   page**, not a training-data recollection of what WHO's policy said as
   of some unknown past date. Terms of use pages change; the ctgov and PDQ
   reviews both quote the live page text they read at review time.

## Concrete next steps (for a session with live network access)

Following `SOURCE_INGESTION_SPEC.md` §8 exactly:

1. **Identify the license.** Fetch and read WHO ICTRP's actual data-reuse
   policy page (search "WHO ICTRP data provision and access policy" and
   confirm the current URL) and, separately, whether it explicitly extends
   to the underlying primary-registry records or only to ICTRP's own
   aggregated view.
2. **Determine the access mechanism.** Confirm whether ICTRP exposes a
   queryable API in 2026 or only the weekly bulk export. This changes the
   client shape entirely (a `ctgov_client.py`-style live-query client vs.
   a `civic_loader.py`-style scheduled-snapshot loader) and therefore the
   hosting mode (`referenced` live-query vs. `hosted` snapshot per §1).
3. **Verify the four constraints** (commercial use / redistribution /
   modifications / share-alike) against what's actually published, not
   assumed-by-analogy to ctgov.
4. **Add a row to `SOURCE_INGESTION_SPEC.md` §2.4`** once 1-3 are done —
   the table currently has no ICTRP row and an EUCTR row whose "scraping
   only" hot-spot was never actually resolved.
5. **Build the client** mirroring `knowledge_base/clients/ctgov_client.py`'s
   shape (parse-to-flat-dict, `SourceClient`-conforming wrapper) *only
   after* 1-3 clear, so the eventual `enumerate_experimental_options()`
   integration (`knowledge_base/engine/experimental_options.py`) can treat
   it as a second `search_fn`-shaped source and merge results the same way
   the biomarker fan-out in this same changeset already merges/dedupes by
   NCT-equivalent ID (ICTRP calls its own identifier the "Universal Trial
   Number" / UTN, but cross-registered trials also carry their native
   NCT/EudraCT number, which is the natural merge key against existing
   ctgov results).
6. **Source entity** with `legal_review.status: pending` until a named
   reviewer with the actual terms in front of them signs off — not
   `reviewed` by default the way this doc's own absence-of-access forces
   it to stay unset entirely for now.

## Open questions a future session must resolve, not guess at

- Does ICTRP's 2026 access model support a per-condition/per-intervention
  live query, or only a full-corpus bulk file the project would need to
  ingest and index itself (which would push this toward `hosted` with a
  CIViC-style monthly-refresh CI job, not a `referenced` live client)?
- Do individual constituent-registry records (e.g. a CTRI/India record
  surfaced via ICTRP) carry CTRI's own terms distinct from WHO's
  aggregation-layer terms? If so, does OpenOnco's structured-metadata-only
  use (NCT/UTN, status, phase, sites — mirroring the ctgov precedent)
  stay clear of that distinction, or does it need a narrower per-registry
  carve-out?
- Is there a simpler win first: EUCTR's replacement system, the EU
  **CTIS** (Clinical Trials Information System), which succeeded EUCTR for
  trials authorized from 2022 onward and may have a more modern API than
  the "scraping only" EUCTR the current spec describes? Worth checking
  before assuming EUCTR (or ICTRP-via-EUCTR) is still the right target for
  new EU trials.

## Effort estimate

Given the unknowns above, this is closer to the audit's own Item-3/Item-4
sizing (2-3 days) than Item-1's (~1 hour) — and that estimate assumes the
access-mechanism question (bulk file vs. live API) resolves in the
simpler direction. If ICTRP turns out to be bulk-file-only, add another
1-2 days for a `hosted`-mode ingestion + snapshot pipeline mirroring
`knowledge_base/ingestion/civic_loader.py`.

## What landed in this changeset instead

Coverage and correctness fixes to the existing single-source (ctgov)
pipeline that don't require new legal review:

- `query.term` vs `query.intr` field-mismatch fix (biomarkers were being
  searched as intervention/drug names).
- API-side status filter now matches what `_OPEN_STATUSES` actually keeps
  client-side (was silently discarding two of the three "open" statuses
  at the API layer).
- Multi-biomarker patients now get merged, deduplicated results across
  all of their positive biomarkers instead of only the first one found.
- Real pagination via `nextPageToken` — `max_results` above 25 previously
  silently capped at one 25-record page.
- A structured, patient-specific age/sex eligibility screen (`age_sex_screen`
  on `TrialOutlook`), computed as a post-cache overlay so the
  cross-patient trial cache stays patient-agnostic.

These meaningfully improve "how many trials show up" and "how well they're
matched to this patient" from the *existing* CT.gov source, independent of
whether/when a second registry is added.

## Sign-off

- **Reviewer:** claude
- **Date:** 2026-07-04
- **Access limitation:** no outbound network access to `who.int` or
  `clinicaltrialsregister.eu` in this session's environment (proxy
  rejected the CONNECT tunnel with HTTP 403 for both). This scoping doc
  is deliberately conservative as a result — it identifies what needs
  verification rather than asserting an unverified license posture.
