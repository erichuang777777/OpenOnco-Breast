"""Indication entity — KNOWLEDGE_SCHEMA_SPECIFICATION §7. The central
clinical recommendation unit: disease + line of therapy + patient
applicability → recommended regimen, with full provenance.

`Indication.phases` (added 2026-05-07 — KNOWLEDGE_SCHEMA_SPECIFICATION §17
ratified) decomposes a single line of therapy into ordered phases
(neoadjuvant → surgery → adjuvant for periop FLOT / CROSS, induction →
maintenance for sequential systemic, etc.). Opt-in: existing indications
without `phases:` continue to work unchanged.
"""

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator, model_validator

from ._reviewer_signoff import ReviewerSignoff, _migrate_int_signoffs
from .base import (
    Base,
    Citation,
    EvidenceLevel,
    IndicationIntent,
    StrengthOfRecommendation,
)


# Sentinel SRC-* id assigned to outcome values that pre-date the Phase 2
# schema migration (Pivotal Trial Outcomes Ingestion Plan §"Schema
# evolution"). Defined as a Source entity at
# `knowledge_base/hosted/content/sources/src_legacy_uncited.yaml` so the
# referential integrity check succeeds. Phase 3 (gap-fill) replaces these
# with real SRC-* ids as values get traced back to pivotal trials.
LEGACY_UNCITED_SOURCE_ID = "SRC-LEGACY-UNCITED"


class BiomarkerRequirement(Base):
    biomarker_id: str
    required: bool = True
    value_constraint: Optional[str] = None  # free-form for now, e.g. ">= 30%"


class IndicationApplicability(Base):
    disease_id: str
    line_of_therapy: Optional[int] = None  # 1, 2, 3... — None = line-agnostic (cross-line algo routing)
    stage_requirements: list[str] = Field(default_factory=list)
    biomarker_requirements_required: list[BiomarkerRequirement] = Field(default_factory=list)
    biomarker_requirements_excluded: list[BiomarkerRequirement] = Field(default_factory=list)
    demographic_constraints: dict = Field(default_factory=dict)
    # e.g. {age_min: 18, age_max: null, ecog_max: 2, fit_for_chemo: true}


class OutcomeValue(Base):
    """Citation-bearing wrapper around a clinical-trial outcome value.

    Phase 2 of the Pivotal Trial Outcomes Ingestion Plan
    (`docs/plans/pivotal_trial_outcomes_ingestion_plan_2026-04-30.md`).
    Plain-string outcome values are coerced to
    ``OutcomeValue(value=<str>, source="SRC-LEGACY-UNCITED")`` by
    ``ExpectedOutcomes._coerce_legacy_string`` so the Phase-1 audit can
    flag pre-migration entries; Phase 3 replaces those placeholders with
    real ``SRC-*`` ids as outcomes get traced to their pivotal-trial
    publications.
    """

    value: str
    source: str
    confidence_interval: Optional[str] = None  # e.g. "95% CI 4.7-6.5"
    median_followup_months: Optional[float] = None


# The schema-declared outcome fields on `ExpectedOutcomes`. Disease-
# specific extras admitted via `extra='allow'` are deliberately NOT
# coerced — they keep their raw shape (string, int, dict, …) until a
# future migration formalizes each one.
_OUTCOME_FIELDS: tuple[str, ...] = (
    "overall_response_rate",
    "complete_response",
    "progression_free_survival",
    "overall_survival_5y",
    "overall_survival_median",
    "disease_free_survival_hr",
    "hcv_cure_rate_svr12",
)


class ExpectedOutcomes(Base):
    """Per REFERENCE_CASE_SPECIFICATION §3.7 — aligns with HCV-MZL fields.

    Each outcome field accepts EITHER a plain string (legacy, pre-Phase-2
    YAML — coerced to ``OutcomeValue(value=str, source="SRC-LEGACY-UNCITED")``)
    OR an ``OutcomeValue`` dict (Phase 2+ format). The
    ``_coerce_legacy_string`` validator runs in ``mode="before"`` so the
    coercion happens before Pydantic's per-field type check; ``None`` and
    dict shapes pass through untouched.
    """

    overall_response_rate: Optional[OutcomeValue] = None
    complete_response: Optional[OutcomeValue] = None
    progression_free_survival: Optional[OutcomeValue] = None
    overall_survival_5y: Optional[OutcomeValue] = None
    overall_survival_median: Optional[OutcomeValue] = None  # Phase 2 (new)
    disease_free_survival_hr: Optional[OutcomeValue] = None  # Phase 2 (new — adjuvant)
    hcv_cure_rate_svr12: Optional[OutcomeValue] = None
    # extra='allow' (inherited from Base) handles disease-specific fields

    @field_validator(*_OUTCOME_FIELDS, mode="before")
    @classmethod
    def _coerce_legacy_string(cls, v):
        """Plain string → OutcomeValue(value=str, source="SRC-LEGACY-UNCITED").

        Backward-compat shim for Phase 2: the 312 indication YAMLs all
        carry plain-string outcomes today. Coercing here preserves the
        loader contract (KB validator stays green) while exposing a
        `source` pointer to render-layer code and to Phase 3 gap-fill.
        ``None`` (absent field) and ``dict`` (already-migrated) values
        pass through unchanged.
        """
        if isinstance(v, str):
            return {"value": v, "source": LEGACY_UNCITED_SOURCE_ID}
        return v


class ControversyPosition(Base):
    position: str
    sources: list[str] = Field(default_factory=list)
    evidence_note: Optional[str] = None


class KnownControversy(Base):
    topic: str
    positions: list[ControversyPosition]
    our_default: Optional[str] = None
    rationale: Optional[str] = None


# ── §17 phased indications (RATIFIED 2026-05-07) ─────────────────────────────


class IndicationPhaseStage(str, Enum):
    """Phase position within a single line of therapy.

    `neoadjuvant` / `surgery` / `adjuvant` come straight from §17.1; the
    `induction` / `maintenance` / `definitive` extensions (planning doc
    §2.2) cover sequential systemic regimens (induction-then-maintenance
    in NSCLC, MPN) and unresectable definitive CRT (esophageal squamous,
    head-and-neck) that don't fit the neoadj-surgery-adj pattern.
    """

    NEOADJUVANT = "neoadjuvant"
    SURGERY = "surgery"
    ADJUVANT = "adjuvant"
    INDUCTION = "induction"
    MAINTENANCE = "maintenance"
    DEFINITIVE = "definitive"


class IndicationPhaseType(str, Enum):
    """Modality of the phase. Drives which foreign key (regimen_id /
    surgery_id / radiation_id) is expected to be populated.

    Extensions over §17.1 (planning doc §2.2): `targeted_therapy` and
    `immunotherapy` separated from generic `chemotherapy` because phased
    indications often interleave them (e.g., induction chemo →
    consolidation IO; CROSS = chemoradiation modality, not chemo+radiation
    as separate phases).
    """

    CHEMOTHERAPY = "chemotherapy"
    SURGERY = "surgery"
    RADIATION = "radiation"
    CHEMORADIATION = "chemoradiation"
    TARGETED_THERAPY = "targeted_therapy"
    IMMUNOTHERAPY = "immunotherapy"


class IndicationPhase(Base):
    """One ordered phase inside an Indication (§17.1 ratified 2026-05-07).

    Foreign-key invariant: exactly ONE of `regimen_id` / `surgery_id` /
    `radiation_id` must be non-null per phase. Enforced by the
    `_exactly_one_fk` model validator below; loader-side ref-integrity
    additionally checks that the populated ID resolves to the right entity
    type (planning doc §2.4 rules 1-4).

    `cycles` and `duration_weeks` are alternatives — `cycles` for
    chemo/targeted/IO, `duration_weeks` for radiation or surgical recovery
    where the cycle concept doesn't apply. Both Optional; render layer
    falls back to `notes:`-style description when neither is set.
    """

    phase: IndicationPhaseStage
    type: IndicationPhaseType

    regimen_id: Optional[str] = None
    surgery_id: Optional[str] = None
    radiation_id: Optional[str] = None

    cycles: Optional[int] = None
    duration_weeks: Optional[int] = None

    @model_validator(mode="after")
    def _exactly_one_fk(self) -> "IndicationPhase":
        """Exactly ONE of regimen_id / surgery_id / radiation_id must be set.

        Schema-level pre-check — ref-integrity (does the ID actually
        resolve to a Regimen / Surgery / RadiationCourse?) lives in the
        loader per existing-pattern. This validator catches the structural
        XOR violation before the loader is ever called.
        """
        populated = sum(
            1
            for fk in (self.regimen_id, self.surgery_id, self.radiation_id)
            if fk is not None
        )
        if populated != 1:
            raise ValueError(
                f"IndicationPhase requires exactly one of regimen_id / "
                f"surgery_id / radiation_id to be set (found {populated})"
            )
        return self


class Indication(Base):
    id: str
    applicable_to: IndicationApplicability

    recommended_regimen: Optional[str] = None  # Regimen ID
    concurrent_therapy: list[str] = Field(default_factory=list)
    followed_by: list[str] = Field(default_factory=list)  # next-line Indication IDs

    # §17 phased indications — opt-in (RATIFIED 2026-05-07). When populated,
    # `phases` describes the ordered intra-line sequence (neoadj → surgery →
    # adj for periop FLOT/CROSS, induction → maintenance for sequential
    # systemic, etc.). Engine pass-through to PlanTrack.indication_data and
    # render-layer phased timeline are deferred to Phase C readiness work
    # (planning doc §2.7).
    phases: Optional[list[IndicationPhase]] = None

    evidence_level: Optional[EvidenceLevel] = None
    strength_of_recommendation: Optional[StrengthOfRecommendation] = None
    nccn_category: Optional[str] = None  # "1" | "2A" | "2B" | "3"

    expected_outcomes: Optional[ExpectedOutcomes] = None

    hard_contraindications: list[str] = Field(default_factory=list)  # Contraindication IDs
    red_flags_triggering_alternative: list[str] = Field(default_factory=list)  # RedFlag IDs

    # §20 prevention extension (RATIFIED 2026-05-18). When intent ∈
    # {prevention, screening, surveillance} AND this list is populated,
    # the engine's prevention path only matches this Indication if at
    # least one of the listed RedFlag IDs fired. Empty list = match by
    # disease_id only (existing behavior preserved for treatment
    # Indications and for back-compat). Prevents cross-etiology
    # contamination — e.g., a Lynch-suspicion RF lists DIS-GASTRIC in
    # relevant_diseases (Lynch elevates gastric risk), but its prevention
    # indications must not pull in H. pylori eradication indications
    # which also target DIS-GASTRIC; explicit RF binding disambiguates.
    triggered_by_redflags: list[str] = Field(default_factory=list)

    required_tests: list[str] = Field(default_factory=list)  # Test IDs (priority_class=critical)
    desired_tests: list[str] = Field(default_factory=list)

    rationale: Optional[str] = None
    sources: list[Citation] = Field(default_factory=list)
    known_controversies: list[KnownControversy] = Field(default_factory=list)

    # "What NOT to do" list per REFERENCE_CASE_SPECIFICATION §1.3 critical:
    # explicit prohibitive bullets that frame avoidable harm. Surfaced by
    # render_plan_html as a dedicated section.
    #
    # `do_not_do` is the canonical Ukrainian-language list (legacy primary
    # language, per CHARTER §1). `do_not_do_en` is the optional English
    # companion list — when populated, EN-side render prefers it over the
    # UA list. Bullets pair positionally; if `do_not_do_en` is shorter
    # than `do_not_do`, render falls back to UA for the un-translated
    # tail.
    do_not_do: list[str] = Field(default_factory=list)
    do_not_do_en: list[str] = Field(default_factory=list)

    plan_track: Optional[str] = None  # "standard" | "aggressive" | "trial" | "palliative"

    # §20 prevention extension (RATIFIED 2026-05-18). Audience / purpose of
    # this Indication. Default `treatment` matches every Indication authored
    # before 2026-05-18 — no backfill required across the ~400 existing
    # Indication YAMLs. Prevention / screening / surveillance values power
    # the Prevention Plan deliverable scoped by CHARTER §3 (Path A,
    # HCP-mediated). Engine intent-filter integration deferred to v0.2
    # implementation waves.
    intent: IndicationIntent = IndicationIntent.TREATMENT

    # FDA non-device CDS positioning (per specs/CHARTER.md §15).
    # If `time_critical: true`, this Indication falls OUTSIDE the §520(o)(1)(E)
    # carve-out — HCP cannot meaningfully independently-review-the-basis under
    # time pressure, so the software function would be device-classified.
    time_critical: bool = False

    last_reviewed: Optional[str] = None
    reviewers: list[str] = Field(default_factory=list)
    # CHARTER §6.1: ≥2 sign-offs to publish. Migrated from int counter to
    # structured list — see _reviewer_signoff.py. Legacy YAML with
    # `reviewer_signoffs: 0` is coerced to [] by the validator below.
    reviewer_signoffs: list[ReviewerSignoff] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_shape(cls, v):
        return normalize_legacy_indication_payload(v)

    @field_validator("reviewer_signoffs", mode="before")
    @classmethod
    def _migrate_signoffs(cls, v):
        return _migrate_int_signoffs(v)


def _legacy_biomarker_requirement(value: object, *, required: bool) -> object:
    if not isinstance(value, str):
        return value
    return {
        "biomarker_id": "LEGACY-FREE-TEXT",
        "required": required,
        "value_constraint": value,
    }


def _note_append(notes: object, prefix: str, values: list[str]) -> str:
    base = notes if isinstance(notes, str) else ""
    addition = f"{prefix}: " + " | ".join(values)
    return f"{base}\n{addition}".strip() if base else addition


def normalize_legacy_indication_payload(raw: object) -> object:
    """Normalize older rich Indication YAML into the current strict schema.

    Several generated indication files used prose objects in fields that later
    became FK-only lists. Preserve that authoring context in `notes`, but keep
    the actual FK fields strict so the loader can still catch real IDs.
    """
    if not isinstance(raw, dict):
        return raw

    normalized = dict(raw)

    if normalized.get("strength_of_recommendation") == "moderate":
        normalized["strength_of_recommendation"] = "conditional"

    sources = []
    for source in normalized.get("sources") or []:
        if isinstance(source, dict) and source.get("position") == "background":
            source = dict(source)
            source["position"] = "context"
        sources.append(source)
    if sources:
        normalized["sources"] = sources

    applicable = normalized.get("applicable_to")
    if isinstance(applicable, dict):
        applicable = dict(applicable)
        for field_name, required in (
            ("biomarker_requirements_required", True),
            ("biomarker_requirements_excluded", False),
        ):
            applicable[field_name] = [
                _legacy_biomarker_requirement(item, required=required)
                for item in applicable.get(field_name) or []
            ]
        normalized["applicable_to"] = applicable

    if isinstance(normalized.get("concurrent_therapy"), list):
        concurrent: list[str] = []
        legacy_notes: list[str] = []
        for item in normalized.get("concurrent_therapy") or []:
            if isinstance(item, str):
                concurrent.append(item)
            elif isinstance(item, dict):
                regimen_id = item.get("regimen_id")
                if isinstance(regimen_id, str):
                    concurrent.append(regimen_id)
                legacy_notes.append(str(item))
        normalized["concurrent_therapy"] = concurrent
        if legacy_notes:
            normalized["notes"] = _note_append(
                normalized.get("notes"),
                "Legacy concurrent therapy details",
                legacy_notes,
            )

    if isinstance(normalized.get("red_flags_triggering_alternative"), list):
        red_flags: list[str] = []
        legacy_notes = []
        for item in normalized.get("red_flags_triggering_alternative") or []:
            if isinstance(item, str):
                red_flags.append(item)
            elif isinstance(item, dict):
                legacy_notes.append(str(item))
        normalized["red_flags_triggering_alternative"] = red_flags
        if legacy_notes:
            normalized["notes"] = _note_append(
                normalized.get("notes"),
                "Legacy alternative-trigger prose",
                legacy_notes,
            )

    return normalized
