"""Plan entity — versioned per-patient treatment plan with multiple tracks.

A Plan is the **rendered output** of the rule engine for a specific patient
at a point in time. Per CHARTER §2, every Plan presents at least two
alternative tracks (standard, aggressive) in **one document** — easier for
tumor-board discussion, single revision history, single audit trail.

A Plan is also a **versioned, living artifact** (per the project's core
product vision): when new patient data arrives — fresh labs, doctor decision,
updated history, new imaging — a new Plan version is generated. The previous
version is retained (immutable), linked via supersedes/superseded_by.

**Privacy note:** Plan instances contain patient-specific data. They live
**outside** the public knowledge base (see CHARTER §9.3). Default location:
`patient_plans/<patient_id>/v<N>.yaml`, gitignored. Only the schema (this
file) and templates are in the public repo.

**FDA non-device CDS positioning** (CHARTER §15): the Plan output structure
is what makes OpenOnco satisfy §520(o)(1)(E) Criterion 4 — every Plan
surfaces the intended use, HCP user, patient population, algorithm summary,
data limitations, and per-track rationale + sources, so the HCP can
independently review the basis.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import Base


class PlanTrack(Base):
    """One alternative treatment plan presented in the document.

    Tracks are not mutually exclusive in presentation — they're shown
    together. `is_default` marks the engine's current best selection;
    HCP makes the actual choice.
    """

    track_id: str  # "standard" | "aggressive" | "trial" | "palliative"
    label: str  # "Стандартний план"
    label_en: Optional[str] = None
    indication_id: str  # → Indication.id
    is_default: bool = False
    selection_reason: Optional[str] = None
    # Materialized at render time so the rendered document is self-contained
    indication_data: Optional[dict] = None
    regimen_data: Optional[dict] = None
    monitoring_data: Optional[dict] = None
    supportive_care_data: list[dict] = Field(default_factory=list)
    contraindications_data: list[dict] = Field(default_factory=list)


class PlanAnnotation(Base):
    """Clinician comment / revision request / approval / concern attached
    to the Plan or to a specific track. Append-only; resolution is a new
    annotation, not in-place edit."""

    track_id: Optional[str] = None  # null = annotation on whole plan
    author: str
    timestamp: str
    annotation_type: Literal["comment", "revision_request", "approval", "concern", "data_update"]
    text: str
    resolved_by: Optional[str] = None  # id of subsequent annotation that resolves this one


class FDAComplianceMetadata(Base):
    """Fields surfaced in every rendered Plan so an HCP can independently
    review the basis (FDA §520(o)(1)(E) Criterion 4 — see CHARTER §15)."""

    intended_use: str
    hcp_user_specification: str
    patient_population_match: str
    algorithm_summary: str
    data_sources_summary: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    automation_bias_warning: Optional[str] = None
    time_critical: bool = False  # if true, falls outside non-device CDS carve-out


class AccessMatrixRow(Base):
    """One row in the per-Plan Access Matrix (ua-ingestion plan §3.1 + §4).

    Aggregates UA-availability metadata for one (track, regimen) pair —
    summarising the registered / reimbursed status, cost orientation, and
    primary access pathway of the regimen's drug components.

    Render-time only. The engine never reads any field on this row as a
    selection signal (plan §0 invariant)."""

    track_id: str                              # "standard" | "aggressive" | "trial:NCT…"
    track_label: str
    regimen_id: Optional[str] = None
    regimen_name: Optional[str] = None
    drug_ids: list[str] = Field(default_factory=list)

    # Aggregated availability across all drug components of the regimen:
    #   True   — all components registered / reimbursed
    #   False  — at least one component not registered / not reimbursed
    #   None   — no UA-availability metadata was carried on any component
    registered_in_ua: Optional[bool] = None
    reimbursed_nszu: Optional[bool] = None

    # Cost summary across components — sum of `cost_uah_self_pay.min` /
    # `.max` when set, else null. Currency assumed UAH (CostRange default).
    cost_self_pay_min: Optional[float] = None
    cost_self_pay_max: Optional[float] = None
    cost_reimbursed_min: Optional[float] = None
    cost_reimbursed_max: Optional[float] = None
    cost_per_unit: Optional[str] = None        # cycle | course | month — first-seen
    cost_last_updated: Optional[str] = None    # oldest component cost_last_updated
    cost_is_stale: bool = False                # True when oldest >180 days ago

    # Pathway hint (resolved AccessPathway.id when one of the drugs
    # has a matching `applies_to_drug_ids` entry; None otherwise).
    primary_pathway_id: Optional[str] = None
    pathway_alternative_ids: list[str] = Field(default_factory=list)

    # Free-text caveat surfaced on render (e.g. "1 of 3 components not
    # listed in НСЗУ formulary" or "verify with foundation directly").
    notes: list[str] = Field(default_factory=list)


class AccessMatrix(Base):
    """Per-Plan aggregation of UA-availability metadata across all tracks.

    Built by `_build_access_matrix(plan, entities)` after track materialization.
    Render-time only; persisted on Plan for plan-export reproducibility."""

    rows: list[AccessMatrixRow] = Field(default_factory=list)
    generated_at: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VariantActionabilityHit(Base):
    """One BiomarkerActionability cell matched against the patient's
    variant profile, surfaced in the Plan for tumor-board context.

    Render-time only — the engine never selects on these tier values
    (CHARTER §8.3 forbids LLM-or-tier-driven treatment ranking; tracks
    come from the declarative Algorithm). The ESCAT tier table sits next
    to the chosen track to inform HCP review.

    Phase 1 of the CIViC pivot (2026-04-27): `oncokb_level` was dropped
    in favour of `evidence_sources`. ESCAT remains the primary tier.
    """

    bma_id: str                       # FK → BiomarkerActionability.id
    biomarker_id: str                 # FK → BIO-* (denormalized for render)
    variant_qualifier: Optional[str] = None  # null = gene-level cell
    escat_tier: str                   # "IA"|"IB"|"IIA"|"IIB"|"IIIA"|"IIIB"|"IV"|"X"
    evidence_sources: list[dict] = Field(default_factory=list)
    evidence_summary: str
    recommended_combinations: list[str] = Field(default_factory=list)
    primary_sources: list[str] = Field(default_factory=list)  # SRC-* IDs


class Plan(Base):
    id: str  # "PLAN-PZ-001-V1"
    patient_id: str  # "PZ-001"
    version: int = 1
    generated_at: str  # ISO-8601

    # Versioning chain (immutable history per CHARTER §10.2)
    supersedes: Optional[str] = None  # previous Plan id
    superseded_by: Optional[str] = None  # set when a newer version replaces this one
    revision_trigger: Optional[str] = None  # e.g. "new lab result 2026-05-01"

    # What the engine ran on
    patient_snapshot: dict
    # str for treatment plans (always selected via an Algorithm). None for
    # PreventionPlan output (§20 ratification 2026-05-18) — prevention path
    # routes by fired prevention RedFlag, not by Algorithm. Existing
    # treatment-plan tests assert specific ALGO-* ids and continue to pass.
    algorithm_id: Optional[str] = None
    knowledge_base_state: dict = Field(default_factory=dict)

    # The tracks — at least 2 per CHARTER §2
    tracks: list[PlanTrack]

    # Same algorithm, different authored line_of_therapy. These tracks are
    # useful sequencing/audit context but must not appear as current-line
    # treatment choices.
    sequencing_tracks: list[PlanTrack] = Field(default_factory=list)

    # FDA Criterion 4 metadata (always present, surfaced in rendered doc)
    fda_compliance: FDAComplianceMetadata

    # Engine internals (also surfaced for transparency)
    trace: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Living document — append-only annotations
    annotations: list[PlanAnnotation] = Field(default_factory=list)

    # Access Matrix (ua-ingestion plan §3.1 + §4) — render-time UA-availability
    # aggregation across tracks. Optional so older Plan YAML still loads.
    # Engine never reads back from this field (plan §0 invariant).
    access_matrix: Optional["AccessMatrix"] = None

    # Variant actionability (ESCAT) — render-time list of
    # BiomarkerActionability cells matched against the patient's
    # biomarker profile. Empty list when no variants matched. Engine
    # never reads back (CHARTER §8.3 — tracks come from Algorithm,
    # tiers are HCP-review context only).
    variant_actionability: list[VariantActionabilityHit] = Field(default_factory=list)
