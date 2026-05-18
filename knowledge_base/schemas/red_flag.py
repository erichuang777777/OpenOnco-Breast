"""RedFlag entity — KNOWLEDGE_SCHEMA_SPECIFICATION §9."""

from typing import Optional

from pydantic import Field, field_validator

from ._reviewer_signoff import ReviewerSignoff, _migrate_int_signoffs
from .base import (
    Base,
    PreventionRiskCategory,
    RedFlagCategory,
    RedFlagDirection,
    RedFlagSeverity,
)


class RedFlagTrigger(Base):
    type: str  # symptom_composite | lab_value | imaging_finding | biomarker_threshold | ...
    all_of: list[dict] = Field(default_factory=list)
    any_of: list[dict] = Field(default_factory=list)
    none_of: list[dict] = Field(default_factory=list)


class RedFlag(Base):
    id: str
    definition: str
    definition_ua: Optional[str] = None

    trigger: RedFlagTrigger
    clinical_direction: RedFlagDirection

    # Conflict-resolution fields (added P0). When two or more RedFlags fire
    # with conflicting clinical_direction, the engine resolves by:
    #   1. clinical_direction precedence (hold > intensify > de_escalate > investigate)
    #   2. severity (critical > major > minor)
    #   3. priority (lower wins; default 100)
    severity: RedFlagSeverity = RedFlagSeverity.MAJOR
    priority: int = 100

    # 5-type matrix per REDFLAG_AUTHORING_GUIDE §2. Authored explicitly so
    # coverage tooling doesn't need keyword heuristics. Defaults to OTHER
    # for un-categorized RFs (legacy compatibility); CI prefers explicit value.
    category: RedFlagCategory = RedFlagCategory.OTHER

    # §20 prevention extension (RATIFIED 2026-05-18). 7-category risk-factor
    # taxonomy for the prevention persona (IARC Monographs + WCRF/AICR +
    # USPSTF + NCCN Genetic/Familial High-Risk). Distinct from `category`
    # above (treatment-time 5-type matrix). Optional — existing
    # treatment-time RedFlags continue to work with this field unset.
    # A single RedFlag may carry BOTH a treatment-time `category` and a
    # prevention-time `risk_category` if it applies to both personas.
    risk_category: Optional[PreventionRiskCategory] = None

    # Optional explicit branch wiring. When set, lets test/coverage tooling
    # confirm that this RedFlag actually drives a specific decision-tree
    # step.id in the named Algorithm. Pure metadata — engine still walks
    # the tree as authored. Format: {"ALGO-X": "step-id-or-int"}.
    branch_targets: dict[str, str] = Field(default_factory=dict)

    relevant_diseases: list[str] = Field(default_factory=list)  # ["*"] = universal
    shifts_algorithm: list[str] = Field(default_factory=list)  # Algorithm IDs affected

    sources: list[str] = Field(default_factory=list)
    last_reviewed: Optional[str] = None
    # CHARTER §6.1: ≥2 sign-offs to publish. Structured form — legacy
    # `reviewer_signoffs: 0` (int) coerced to [] by the validator below.
    reviewer_signoffs: list[ReviewerSignoff] = Field(default_factory=list)
    notes: Optional[str] = None

    # Authoring lifecycle. Drafts (`draft: true`) are loaded by the engine
    # but flagged in CI; non-draft RedFlags must satisfy the source-citation
    # requirement (CHARTER §6.1) and pass clinical review.
    draft: bool = False

    @field_validator("reviewer_signoffs", mode="before")
    @classmethod
    def _migrate_signoffs(cls, v):
        return _migrate_int_signoffs(v)
