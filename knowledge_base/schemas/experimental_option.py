"""ExperimentalOption — clinical-trial track in a Plan.

Per docs/plans/ua_ingestion_and_alternatives_2026-04-26.md §2.3.

A single-(disease, biomarker_profile, line_of_therapy) container holding
the active recruiting / active-not-recruiting trials returned from
ClinicalTrials.gov. Generated, not curated. Render exposes these as a
third Plan track alongside the engine-selected standard + alternative.

Engine semantics: `ExperimentalOption` is render-time-only metadata. It
NEVER influences which Indication / Regimen the engine picks for the
default or alternative tracks (CHARTER §8.3 + the "show all alternatives"
invariant from `feedback_efficacy_over_registration.md`).

`TrialOutlook` (added 2026-05-07) is a per-trial structured signal
bundle — biomarker-stratification detection + design-quality flags,
computed by `engine.trial_outlook.score_trial`. Like the rest of this
track, it's render-time-only metadata: never read back as a selection
signal. v1 ships two signals (`biomarker_stratification`,
`design_flags`); mechanism-precedent scoring is deferred to a follow-up.
"""

from typing import Literal, Optional

from pydantic import Field

from .base import Base


# ── Trial outlook: per-trial structured signals ──────────────────────────────
#
# Pure heuristics over the parsed ctgov dict — no probabilistic claims, no
# verbal verdicts. Render surfaces each flag as a tag with an explanatory
# tooltip; the engine never consumes these fields.

BiomarkerStratification = Literal[
    "enriched",   # patient's biomarker is in the inclusion criteria
    "open_label", # no biomarker enrichment detected (or none queried)
    "unclear",    # biomarker mentioned only in exclusion / ambiguous match
]

DesignFlag = Literal[
    "phase1_only",            # phase string is exactly PHASE1
    "small_enrollment",       # target N < 50
    "surrogate_endpoint_only", # primary outcomes ORR/PFS but no OS
    "single_country",         # site presence in only one country
]


class TrialOutlook(Base):
    """Structured per-trial signals for the experimental-options render layer.

    See `engine.trial_outlook.score_trial` for the heuristics. v1 fields
    are intentionally minimal — every flag must be derivable from the
    parsed ctgov study dict alone (no KB lookup, no probabilistic
    modeling). Mechanism-precedent scoring is a follow-up.
    """

    biomarker_stratification: BiomarkerStratification
    design_flags: list[DesignFlag] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # one short string per flag
    last_scored: Optional[str] = None  # ISO date


class UaSiteDetail(Base):
    """One Ukrainian recruiting site for an `ExperimentalTrial`.

    Closes Gap 2 from `docs/reviews/ctgov-wiring-audit-2026-05-18.md` — the
    previous render shape exposed a single "UA" badge per trial, discarding
    facility, city, and per-site status. Per `CHARTER §1` the UA-local
    angle is one of OpenOnco's structural differentiators, so the patient
    looking at their Plan should see *where* in Ukraine to ask about
    screening, not just that a UA site exists somewhere.

    All fields optional because ctgov v2's flat-fields response sometimes
    returns parallel arrays of different lengths (e.g. facility list
    longer than city list when one site lacks a city tag). The mapper
    zips defensively and fills `None` where data is missing.
    """

    facility: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    status: Optional[str] = None  # RECRUITING | ACTIVE_NOT_RECRUITING | …


class ExperimentalTrial(Base):
    """One ClinicalTrials.gov study entry, parsed from the v2 API."""

    nct_id: str
    title: str
    status: str  # "RECRUITING" | "ACTIVE_NOT_RECRUITING" | other
    phase: Optional[str] = None
    sponsor: Optional[str] = None
    summary: Optional[str] = None
    inclusion_summary: Optional[str] = None
    exclusion_summary: Optional[str] = None
    countries: list[str] = Field(default_factory=list)  # ISO-2 codes from ctgov
    sites_ua: list[str] = Field(default_factory=list)   # UA city names if any
    # Structured per-UA-site detail (facility, city, state, status).
    # Populated when ctgov returns location-level fields; empty list when
    # the search-mode response only carried country names. Render falls
    # back to the binary `sites_ua` badge when this list is empty.
    # Default-empty for cache-shape backward compatibility.
    ua_sites_detail: list[UaSiteDetail] = Field(default_factory=list)
    sites_global_count: Optional[int] = None
    last_synced: Optional[str] = None  # ISO date

    # Structured outlook signals — render-time-only, populated by
    # `engine.trial_outlook.score_trial`. Optional so older cached JSON
    # without this field still loads.
    outlook: Optional[TrialOutlook] = None


class ExperimentalOption(Base):
    """One bundle of trials for a (disease, biomarker, stage, line) scenario.

    Generated via `enumerate_experimental_options()`; the `id` is
    deterministic from the query parameters so re-querying produces a
    stable identifier for caching + provenance.
    """

    id: str
    disease_id: str
    molecular_subtype: Optional[str] = None
    stage_stratum: Optional[str] = None
    line_of_therapy: Optional[int] = None
    trials: list[ExperimentalTrial] = Field(default_factory=list)
    last_synced: Optional[str] = None
    notes: Optional[str] = None
    sources: list[str] = Field(default_factory=lambda: ["SRC-CTGOV"])
