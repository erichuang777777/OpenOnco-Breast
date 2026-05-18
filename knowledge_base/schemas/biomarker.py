"""Biomarker entity — KNOWLEDGE_SCHEMA_SPECIFICATION §4."""

from typing import Literal, Optional

from pydantic import Field, model_validator

from .base import Base, BiomarkerClinicalContext, NamePair


# Stable machine-readable tokens for biomarkers we deliberately exclude
# from actionability lookups. These strings are greppable and downstream
# code (engine/actionability_extract.py) keys behavior off them — DO NOT
# rename without coordinating with that module.
OncoKBSkipReason = Literal[
    "ihc_no_variant",
    "score",
    "clinical_composite",
    "serological",
    "viral_load",
    "tumor_marker",
    "imaging",
    "germline_no_somatic",
    "fusion_mvp",
    "itd_mvp",
    "multi_allele_mvp",
    "tumor_agnostic",
]


class BiomarkerMeasurement(Base):
    method: Optional[str] = None  # IHC | PCR | NGS | flow_cytometry | serology
    units: Optional[str] = None
    typical_range: Optional[list[float]] = None


class MutationDetails(Base):
    gene: Optional[str] = None
    gene_hugo_id: Optional[str] = None
    exon: Optional[str] = None
    variant_type: Optional[str] = None  # missense | fusion | amplification | deletion | ...
    functional_impact: Optional[str] = None  # activating | loss_of_function | ...
    hgvs_protein: Optional[str] = None
    hgvs_coding: Optional[str] = None


class ActionabilityLookupHint(Base):
    """Explicit hint to enable actionability lookups for this biomarker.

    Per oncokb_integration_safe_rollout_v3.md §4: variant normalization is
    conservative — biomarkers without an explicit hint are SKIPPED. This
    is intentional: silent guessing of (gene, variant) from biomarker id
    risks false negatives that clinicians wouldn't notice.

    `gene` must be the HGNC symbol (uppercase). `variant` should be the
    short HGVS-p form (e.g. "V600E", "L858R", "G12C"), a structured
    descriptor (e.g. "Exon 19 deletion", "E746_A750del"), or a frameshift
    token (e.g. "W288fs"). Full HGVS validation lives in
    `engine/actionability_extract.py:normalize_variant`; this schema only
    type-checks. Anything that fails normalization at runtime (HGVS-c,
    fusion, boolean flag) should not be represented here — leave the hint
    absent and use `oncokb_skip_reason` instead.

    Source-agnostic: same hint shape feeds CIViC, OncoKB-style readers,
    or any future actionability source.
    """

    gene: str = Field(..., min_length=1, max_length=32)
    variant: str = Field(..., min_length=1, max_length=128)


class BiomarkerExternalIDs(Base):
    """Stable cross-references to external knowledge bases.

    Per oncokb_integration_safe_rollout_v3.md §4: surfacing external
    records (CIViC / ClinGen / etc.) uses these IDs as canonical anchors.
    All fields are optional — a partial mapping (e.g., only `hgnc_symbol`)
    is valid for biomarkers we haven't fully classified yet.
    """

    hgnc_symbol: Optional[str] = None
    hgnc_id: Optional[str] = None
    oncokb_url: Optional[str] = None
    civic_id: Optional[str] = None
    civic_url: Optional[str] = None
    clingen_id: Optional[str] = None
    hgvs_protein: Optional[str] = None
    hgvs_coding: Optional[str] = None


class Biomarker(Base):
    id: str
    names: NamePair
    biomarker_type: Optional[str] = None
    # protein_expression_ihc | protein_serology | gene_mutation | gene_fusion |
    # copy_number | msi_status | tmb | methylation | ...

    measurement: Optional[BiomarkerMeasurement] = None
    mutation_details: Optional[MutationDetails] = None
    specimen_requirements: list[str] = Field(default_factory=list)

    # Actionability integration — opt-in hint per biomarker.
    # If absent, the actionability extractor skips this biomarker entirely.
    # Renamed from `oncokb_lookup` (CIViC pivot — see
    # docs/reviews/oncokb-public-civic-coverage-2026-04-27.md).
    actionability_lookup: Optional[ActionabilityLookupHint] = None

    # Mutually exclusive with `actionability_lookup`: a stable
    # machine-readable token explaining WHY this biomarker is intentionally
    # excluded from actionability lookups. The token vocabulary is
    # source-agnostic (an IHC biomarker is unsuitable for variant-level
    # lookup whether the source is CIViC or OncoKB), so the field name
    # `oncokb_skip_reason` is preserved for back-compat with existing YAML.
    oncokb_skip_reason: Optional[OncoKBSkipReason] = None

    # Cross-references to external KBs (HGNC, OncoKB, CIViC, ClinGen).
    # Optional and partial — see BiomarkerExternalIDs.
    external_ids: Optional[BiomarkerExternalIDs] = None

    # §20 prevention extensions (RATIFIED 2026-05-18). Multi-valued — one
    # marker may serve several clinical contexts (e.g., MMR / MSI is
    # simultaneously germline_susceptibility + tumor_profiling +
    # predictive). Default `[tumor_profiling]` matches current implicit
    # behavior across the ~170 existing Biomarker YAMLs — no backfill
    # required. `applicable_in_asymptomatic` is the fast filter for
    # Prevention Plan composition: only true for markers with established
    # asymptomatic use (germline panels, syndrome-specific monitoring like
    # calcitonin in MEN2, AFP+US in cirrhotics).
    clinical_context: list[BiomarkerClinicalContext] = Field(
        default_factory=lambda: [BiomarkerClinicalContext.TUMOR_PROFILING]
    )
    applicable_in_asymptomatic: bool = False

    related_biomarkers: list[str] = Field(default_factory=list)
    knowledge_base_refs: dict[str, str] = Field(default_factory=dict)  # oncokb | civic | clinvar URL
    sources: list[str] = Field(default_factory=list)

    last_reviewed: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _actionability_lookup_xor_skip(self) -> "Biomarker":
        """`actionability_lookup` and `oncokb_skip_reason` are mutually exclusive.

        Zero-or-one is fine — a biomarker that hasn't been triaged for
        actionability integration yet may have neither set. But declaring
        both is contradictory (the lookup would be requested AND
        deliberately skipped) and almost certainly an authoring error.
        """
        if self.actionability_lookup is not None and self.oncokb_skip_reason is not None:
            raise ValueError(
                "Biomarker may set at most one of `actionability_lookup` and "
                "`oncokb_skip_reason` — not both."
            )
        return self


# Back-compat re-export. Any code importing `OncoKBLookupHint` keeps
# working through Phase 1 → 2 transition. The schema field name has
# already changed to `actionability_lookup`; only the class identifier
# is shadowed here.
OncoKBLookupHint = ActionabilityLookupHint
