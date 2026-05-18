# ClinicalTrials.gov client — wiring audit, 2026-05-18

Maps what the ctgov integration currently does end-to-end, what it
doesn't, and the smallest follow-on workstreams that would close the
real gaps. Pure analysis — no code changes. Companion to the source
scaffolds shipping for NCI PDQ (PR #589) and CPIC (PR #590).

## TL;DR

The ctgov layer is **partially wired** and works in the happy path:

- The client (`knowledge_base/clients/ctgov_client.py`) is mature: dual
  function-level API (`search_trials` / `get_trial`) plus a
  `BaseSourceClient` wrapper (`CtgovClient`).
- The engine consumes it via `experimental_options.enumerate_experimental_options`
  → emits an `ExperimentalOption` bundle attached to every Plan.
- The site build prewarms 177 ctgov queries into an on-disk cache
  (`knowledge_base/hosted/content/cache/ctgov/`) and the engine renders
  the experimental track from cache in Pyodide.
- 39 tests pass (`test_experimental_options.py` + `test_trial_outlook.py`).

But there are **three real wiring gaps**:

1. **No `Source` entity YAML** — code references `SRC-CTGOV-REGISTRY`
   but `knowledge_base/hosted/content/sources/src_ctgov.yaml` does not
   exist. The validator passes only because nothing in the YAML KB
   cites the ID; the python code uses it as a free-text constant.
2. **NCT IDs in clinical YAMLs cite their pivotal-trial Source (e.g.
   `SRC-KEYNOTE-024-RECK-2016`), not `SRC-CTGOV-REGISTRY`** — 147 NCT
   strings across 144 Source entities; 46 NCT mentions across 26
   Indication entities. The ctgov client never reads or enriches these.
3. **UA-site detection is binary** — `_ua_sites_from_countries`
   surfaces a single `"UA"` marker if Ukraine is in the country list,
   but does not extract facility names, contact info, or recruitment
   counts. Per `CHARTER §1` UA local focus this is the most
   underexploited dimension.

## What's actually wired (the happy path)

### 1. Client surface

`ctgov_client.py` exposes two layers:

**Function-level (legacy, used by everything in production):**
- `search_trials(condition, intervention, status, phase, max_results)`
  — searches CT.gov v2 API. Returns parsed dicts with NCT ID, title,
  phase, enrollment, sites, eligibility summary.
- `get_trial(nct_id)` — single-record fetch.
- `enrich_report_with_trials(report_path, ...)` — fills NCT details
  into legacy autoresearch JSON reports.

**`BaseSourceClient` subclass (added later, less used):**
- `CtgovClient(BaseSourceClient[CtgovQuery, dict])`
- Wraps the function-level layer behind the unified
  `SourceClient` interface — caching + rate-limiting come from the base.
- `source_id = "SRC-CTGOV-REGISTRY"`, `cache_ttl_seconds = 86400`
  (1 day), `api_version = "v2"`.

The two layers are not fully harmonised: `experimental_options.py`
takes a `search_fn` callable matching `search_trials`'s signature, not
a `CtgovClient` instance. This means the `BaseSourceClient`-shape
caching is bypassed in favour of bespoke `_DEFAULT_TTL_DAYS` on-disk
JSON files.

### 2. Engine consumption

`knowledge_base/engine/experimental_options.py`:

- `enumerate_experimental_options(disease_id, disease_term,
  biomarker_profile, ..., search_fn)` returns an `ExperimentalOption`
  bundle.
- Cache strategy: in-process `_QUERY_CACHE` (per-process) + disk cache
  under `cache_root` (typically
  `knowledge_base/hosted/content/cache/ctgov/`). 7-day TTL.
- Offline-safe: when `search_fn` is `None` AND `cache_root` is `None`,
  returns an empty `ExperimentalOption` with note `"ctgov search not
  configured"` — never raises (per plan §3.3).
- When `search_fn` raises, captures the exception in
  `option.notes = f"ctgov search failed: {exc}"` and still returns
  a valid empty `ExperimentalOption`. Engine never blocks on upstream.

`knowledge_base/engine/plan.py` (line 692-709):
- `compute_plan(..., experimental_search_fn=, experimental_cache_root=)`
- Triggered iff either parameter is non-None.
- Per-track or per-disease scope is determined by the disease's
  representative biomarker term (`plan.py:793` `_pick_representative_biomarker`).

`knowledge_base/engine/trial_outlook.py`:
- v1 heuristic scoring over the parsed ctgov dict (no KB lookup, pure
  pattern matching). Two signals: estimated wait time + recruitment
  velocity. Tested in `test_trial_outlook.py` (15 tests pass).

### 3. Cache prewarming

`scripts/sync_ctgov_trials.py`:
- Iterates all `examples/*.json` patient files (the showcase profiles
  used on openonco.info).
- For each, runs the engine in real ctgov mode (`experimental_search_fn=
  search_trials`) so the on-disk cache is populated.
- 177 cached query files exist on disk
  (`knowledge_base/hosted/content/cache/ctgov/ctgov_*.json`), last
  touched 2026-05-17.

`scripts/build_site.py:4796`:
- The static site build reads from this cache (`experimental_cache_root=
  KB / 'cache' / 'ctgov'`) so the Pyodide-in-browser bundle can render
  the experimental track without ctgov reachability.

### 4. Render layer

`knowledge_base/engine/render.py`:
- `_render_experimental_section` (line ~1870) emits an `<section
  class="experimental-track">` block per Plan.
- 3 states: `option is None` (unset placeholder), `option.trials == []`
  (empty-state message), `trials present` (table with NCT, status,
  phase, sponsor, sites, UA badge, eligibility summary, outlook).
- UA badge: when `t.sites_ua` is non-empty, emits a `<span class="badge
  badge--ua">UA</span>` next to the trial.

## What's NOT wired (the real gaps)

### Gap 1: No `Source` entity YAML for `SRC-CTGOV-REGISTRY`

```
$ ls knowledge_base/hosted/content/sources/ | grep -i ctgov
(no matches)
```

The string `"SRC-CTGOV-REGISTRY"` is referenced in:

- `knowledge_base/clients/ctgov_client.py:458` — `source_id` class attr
- `knowledge_base/schemas/experimental_option.py` — schema docs / examples
- `knowledge_base/engine/mdt_orchestrator.py` — provenance event

…but the validator only checks references between YAML entities. Code
constants are not cross-checked. So the validator says
`OK — all entities valid, all references resolve` even though one of
the Source IDs the code emits would fail to resolve to a real entity if
ever queried.

**Impact:** when the render layer eventually surfaces "Cited from
SRC-CTGOV-REGISTRY" — there's no Source entity to link to. Either the
render layer silently drops the citation, or the eventual citation
link is broken. The companion PDQ / CPIC PRs each ship their Source
YAML; ctgov never did.

**Fix shape (small, safe):** add `src_ctgov.yaml` mirroring the same
shape as `src_pdq.yaml` (PR #589) but with the right metadata:

```yaml
id: SRC-CTGOV-REGISTRY
source_type: clinical_trial_registry
title: "ClinicalTrials.gov — US National Library of Medicine"
url: https://clinicaltrials.gov/
access_level: open_access
license:
  name: "US Public Domain (17 U.S.C. §105)"
  url: https://clinicaltrials.gov/about-site/terms-conditions
hosting_mode: referenced
commercial_use_allowed: true
redistribution_allowed: true
modifications_allowed: true
sharealike_required: false
precedence_policy: confirmatory
```

License posture is the same as NCI PDQ — federal-government work, US
public domain — so the license-review doc can fit on one page.

### Gap 2: NCT IDs in clinical YAMLs are not linked to ctgov data

The KB carries 147 NCT IDs across 144 Source entities (the pivotal
trial papers — KEYNOTE-024, CheckMate-067, ADAURA, etc.) and 46 more
across 26 Indication entities. None of these are wired to ctgov
enrichment.

**Today's behaviour:** an Indication that cites the KEYNOTE-024 paper
gets a static prose citation. The patient looking at their Plan sees:
"Pembrolizumab — supported by Reck et al, NEJM 2016." Period.

**What's possible with ctgov wiring:** the same Plan could surface
"…and NCT02220894 is closed-to-accrual (status: completed). 12 follow-
on studies cite this trial protocol; 3 are recruiting in Eastern
Europe." That's a much richer experience and **already implemented
infrastructure-side** — `get_trial(nct_id)` returns exactly this
data. It just isn't called.

**Fix shape (medium, needs design):** a render-time enrichment pass
that walks every Source / Indication NCT ID through the disk cache and
attaches structured status/site data. New cache entries (`ctgov_get_<NCT>.json`)
can be prewarmed by `scripts/sync_ctgov_trials.py`. Engine side stays
clean (CHARTER §8.3 — render-time only, no routing influence).

### Gap 3: UA-site detection is binary, no facility data

`_ua_sites_from_countries(["UA", "US", "DE"])` returns `["UA"]`. The
render-layer badge is a single dot. But:

- A Ukrainian patient wants to know **which city** has a recruiting
  site. Kyiv ≠ Lviv ≠ Kharkiv for travel cost / accessibility.
- A clinician wants the PI contact for screening referral.
- A care navigator needs the recruitment count (still enrolling vs full).

`search_trials` already returns `locations` in the protocolSection of
the v2 API response — `_parse_study` discards everything except the
country list (line 199-202 of ctgov_client). Surfacing the facility
list is a 10-line fix in `_parse_study` plus a render-layer change to
show city + status under the UA badge.

**Per `CHARTER §1`** the UA-local angle is one of OpenOnco's structural
differentiators. This is the highest-impact ctgov improvement
available — turns a one-pixel badge into "Recruiting at NCT04..., 2
Ukrainian sites: Kyiv (Дніпро-1, contact T. Ivanenko), Lviv (LDS, contact
M. Kovalchuk). Last verified: 2026-05-17."

## Test coverage map

- `test_experimental_options.py` (24 tests) — bundle construction,
  cache TTL, biomarker filtering, country normalisation, error
  capture. All pass.
- `test_trial_outlook.py` (15 tests) — wait-time + velocity heuristics.
  All pass.
- `test_mdt_orchestrator.py` — references SRC-CTGOV-REGISTRY in
  provenance event assertions but doesn't validate it resolves to a
  real entity.
- **No test for**: NCT-ID round-trip from clinical YAML through
  enrichment; UA-site city extraction; the gap-1 missing Source entity.

## Recommended next moves (ranked by effort × payoff)

| Rank | Workstream | Effort | Payoff | Risk |
| --- | --- | --- | --- | --- |
| 1 | Add `src_ctgov.yaml` Source entity | ~1 hour | Closes citation-resolution latent bug; mirrors PDQ/CPIC scaffold | None — pure metadata |
| 2 | UA facility-extraction (Gap 3) — `_parse_study` + render | ~1 day | UA-local differentiation; very visible user-facing improvement | Low — render-time only, no routing change |
| 3 | NCT-ID enrichment pass (Gap 2) — render-time decoration | ~2-3 days | Adds live trial status to every cited pivotal trial | Low if render-time only; needs cache prewarming for offline modes |
| 4 | Harmonise `CtgovClient` wrapper with `search_fn` callable shape — pass a `CtgovClient` instance into `enumerate_experimental_options` | ~half day | Single caching seam instead of two; aligns with PDQ / CPIC pattern | Low — refactor, but covered by 39 tests |
| 5 | Add a `tests/test_ctgov_source_entity.py` drift guard once Gap 1 lands | ~1 hour | Same source-id drift guard pattern as PDQ / CPIC PRs | None |

Item 1 is **the natural follow-up to PR #589 + #590**. It uses the
same scaffold shape, completes the citation-resolution invariant, and
sets up Items 2 and 3 to inherit clean Source citations.

## Out of scope here

- **No code changes** in this PR — pure audit.
- **No new clinical content** — would need CHARTER §6.1 two-reviewer
  signoff anyway.
- **No live ctgov calls** — audit is filesystem-grep only.
- **No changes to `scripts/sync_ctgov_trials.py`** — works fine as-is.

## Sign-off

- **Reviewer:** claude
- **Date:** 2026-05-18
- **Files examined:** `knowledge_base/clients/ctgov_client.py`,
  `knowledge_base/engine/{experimental_options,trial_outlook,render,plan,mdt_orchestrator}.py`,
  `knowledge_base/schemas/experimental_option.py`,
  `scripts/sync_ctgov_trials.py`, `scripts/build_site.py`,
  test suites, all `knowledge_base/hosted/content/sources/*.yaml`,
  all `knowledge_base/hosted/content/indications/*.yaml`,
  `knowledge_base/hosted/content/cache/ctgov/`.
- **Tests run:** `pytest tests/test_experimental_options.py
  tests/test_trial_outlook.py` — 39 pass.
