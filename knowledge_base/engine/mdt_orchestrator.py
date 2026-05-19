"""MDT Orchestrator — turns a PlanResult into a structured tumor-board brief.

See specs/MDT_ORCHESTRATOR_SPEC.md for full design. Core invariants:

- Does NOT change clinical recommendations. The PlanResult passed in is
  read-only here; default_indication_id and all track data are untouched.
- Does NOT use LLM for clinical reasoning (CHARTER §8.3). All rules
  are deterministic and listed in the spec §3-§4.
- Adds three things: required/recommended/optional roles for the MDT,
  open questions where data is missing or ambiguous, and an initial
  set of provenance events so the formation of the plan is auditable
  from the very first moment.

MVP scope: rules tuned for the HCV-MZL reference case. Other diseases
fall through to the generic lymphoma / generic-cancer rules; expand
as new diseases land in the KB.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

from knowledge_base.validation.loader import load_content

from .plan import PlanResult
from .provenance import (
    DecisionProvenanceGraph,
    ProvenanceEvent,
    make_event,
    now_iso,
)


TriggerType = Literal[
    "missing_data",
    "diagnosis_complexity",
    "treatment_domain",
    "safety_risk",
    "molecular_data",
    "local_availability",
    "palliative_need",
]

Priority = Literal["required", "recommended", "optional"]
_PRIORITY_RANK = {"required": 3, "recommended": 2, "optional": 1}


@dataclass
class SkillMetadata:
    """Versioned metadata for one MDT specialist skill (= virtual doctor).

    Per CHARTER §6.1, every clinical-content unit needs dual sign-off
    before it can claim "reviewed". Skill modules are rule containers,
    so they version + sign-off the SAME way Indications do. The version
    string follows semver convention and bumps on:

    - patch: typo, wording, source citation update
    - minor: rule added/removed/modified, new linked-finding mapping
    - major: rule semantics changed (e.g., direction flipped from
      "intensify" to "investigate")

    `verified_by` holds the cumulative list of named clinician sign-offs
    with dates. `clinical_lead` is the single accountable owner (per
    CHARTER §6 Project Coordinator + Clinical Co-Lead model).
    """

    skill_id: str  # equals role_id
    name: str
    version: str
    last_reviewed: str
    clinical_lead: Optional[str] = None
    verified_by: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    domain: Optional[str] = None
    notes: Optional[str] = None

    @property
    def signoffs(self) -> int:
        return len(self.verified_by)

    @property
    def review_status(self) -> str:
        return "reviewed" if self.signoffs >= 2 else "stub"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signoffs"] = self.signoffs
        d["review_status"] = self.review_status
        return d


@dataclass
class MDTRequiredRole:
    role_id: str
    role_name: str
    reason: str
    trigger_type: TriggerType
    priority: Priority
    linked_findings: list[str] = field(default_factory=list)
    linked_questions: list[str] = field(default_factory=list)
    skill: Optional[SkillMetadata] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.skill is not None:
            d["skill"] = self.skill.to_dict()
        return d


@dataclass
class OpenQuestion:
    id: str
    question: str
    owner_role: str
    blocking: bool
    rationale: str
    linked_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MDTTalkTreeNode:
    step: int
    owner_role: str
    topic: str
    action: str
    blocking: bool = False
    linked_questions: list[str] = field(default_factory=list)
    linked_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MDTOrchestrationResult:
    patient_id: Optional[str]
    plan_id: Optional[str]
    disease_id: Optional[str]
    required_roles: list[MDTRequiredRole] = field(default_factory=list)
    recommended_roles: list[MDTRequiredRole] = field(default_factory=list)
    optional_roles: list[MDTRequiredRole] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)
    talk_tree: list[MDTTalkTreeNode] = field(default_factory=list)
    data_quality_summary: dict = field(default_factory=dict)
    aggregation_summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    provenance: Optional[DecisionProvenanceGraph] = None

    @property
    def activated_skills(self) -> list[SkillMetadata]:
        """All distinct skills triggered for this plan, deduped across the
        required/recommended/optional buckets, in catalog order."""
        seen: dict[str, SkillMetadata] = {}
        for bucket in (self.required_roles, self.recommended_roles, self.optional_roles):
            for r in bucket:
                if r.role_id in seen or r.skill is None:
                    continue
                seen[r.role_id] = r.skill
        return list(seen.values())

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "plan_id": self.plan_id,
            "disease_id": self.disease_id,
            "required_roles": [r.to_dict() for r in self.required_roles],
            "recommended_roles": [r.to_dict() for r in self.recommended_roles],
            "optional_roles": [r.to_dict() for r in self.optional_roles],
            "open_questions": [q.to_dict() for q in self.open_questions],
            "talk_tree": [n.to_dict() for n in self.talk_tree],
            "data_quality_summary": dict(self.data_quality_summary),
            "aggregation_summary": dict(self.aggregation_summary),
            "warnings": list(self.warnings),
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "activated_skills": [s.to_dict() for s in self.activated_skills],
            "skill_catalog": [s.to_dict() for s in _SKILL_REGISTRY.values()],
        }


# ── Patient profile flattening (mirrors plan.generate_plan) ───────────────


def _flatten_findings(patient: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out.update(_flatten_nested_observations(patient.get("clinical_record") or {}))
    out.update(patient.get("findings") or {})
    for k, v in (patient.get("biomarkers") or {}).items():
        out.setdefault(k, v)
    for k, v in (patient.get("demographics") or {}).items():
        out.setdefault(k, v)
    return out


def _normalize_observation_key(key: str) -> str:
    normalized = []
    previous_was_sep = False
    for ch in key.strip():
        if ch.isalnum():
            normalized.append(ch.lower())
            previous_was_sep = False
        elif not previous_was_sep:
            normalized.append("_")
            previous_was_sep = True
    return "".join(normalized).strip("_")


def _flatten_nested_observations(value: Any, prefix: tuple[str, ...] = ()) -> dict[str, Any]:
    """Expose nested clinical_record observations as lookup keys for MDT QA.

    The planner intentionally reads only normalized top-level fields. This
    helper is narrower: it lets data-quality checks see existing structured
    record values so we do not ask the MDT to provide data already present.
    """
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str):
                out.update(_flatten_nested_observations(child, (*prefix, key)))
        return out
    if isinstance(value, list):
        if value:
            joined_key = "_".join(_normalize_observation_key(part) for part in prefix)
            if joined_key:
                out[joined_key] = value
        for idx, child in enumerate(value):
            out.update(_flatten_nested_observations(child, (*prefix, str(idx))))
        return out
    if value in (None, "") or not prefix:
        return out

    leaf = prefix[-1]
    leaf_norm = _normalize_observation_key(leaf)
    path_norm = "_".join(_normalize_observation_key(part) for part in prefix)
    for key in (leaf, leaf.lower(), leaf_norm, path_norm):
        if key:
            out.setdefault(key, value)
    return out


def _has(findings: dict[str, Any], *keys: str) -> bool:
    """True if ANY of the given keys (or its known aliases) resolves to a
    non-empty value. Uses the same alias map as the trigger evaluator so
    `unevaluated_red_flags` and `evaluate_redflag_trigger` agree on
    "data present"."""
    from .redflag_eval import _resolve_finding
    for k in keys:
        if _resolve_finding(findings, k) is not None:
            return True
    return False


def _truthy(findings: dict[str, Any], key: str) -> bool:
    """True if key present and value is truthy / 'positive' / 'yes' / 'true'."""
    v = findings.get(key)
    if v in (None, "", False, 0):
        return False
    if isinstance(v, str):
        return v.strip().lower() in {"positive", "yes", "true", "+"}
    return bool(v)


def _biomarker_id_from_requirement(req: Any) -> Optional[str]:
    if isinstance(req, str):
        return req
    if isinstance(req, dict):
        return req.get("biomarker_id")
    return None


def _biomarker_requirement_constraint(req: Any) -> Optional[str]:
    if not isinstance(req, dict):
        return None
    for key in ("value_constraint", "value"):
        v = req.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _talk_topic(question_id: str) -> str:
    if question_id.startswith("OQ-BIOMARKER-"):
        return "Biomarker status"
    if "HBV" in question_id or "HCV" in question_id or "FIBROSIS" in question_id:
        return "Infection / hepatic safety"
    if "CD20" in question_id or "PATH" in question_id or "DIFFERENTIAL" in question_id:
        return "Pathology confirmation"
    if "STAGING" in question_id or "LDH" in question_id:
        return "Staging / disease burden"
    if "DRUG-AVAILABILITY" in question_id:
        return "Access feasibility"
    return "Open question"


def _build_talk_tree(
    required_roles: list[MDTRequiredRole],
    recommended_roles: list[MDTRequiredRole],
    optional_roles: list[MDTRequiredRole],
    open_questions: list[OpenQuestion],
) -> list[MDTTalkTreeNode]:
    """Convert role activation + open questions into an ordered MDT script.

    The tree is deterministic and informational. It gives the tumor board a
    discussion order but does not alter engine-selected tracks.
    """
    nodes: list[MDTTalkTreeNode] = []
    step = 1

    sorted_questions = sorted(
        open_questions,
        key=lambda q: (not q.blocking, q.owner_role, q.id),
    )
    for q in sorted_questions:
        nodes.append(MDTTalkTreeNode(
            step=step,
            owner_role=q.owner_role,
            topic=_talk_topic(q.id),
            action=q.question,
            blocking=q.blocking,
            linked_questions=[q.id],
            linked_findings=list(q.linked_findings),
        ))
        step += 1

    question_owners = {q.owner_role for q in open_questions}
    for role in [*required_roles, *recommended_roles, *optional_roles]:
        if role.role_id in question_owners:
            continue
        if role.priority == "optional":
            continue
        nodes.append(MDTTalkTreeNode(
            step=step,
            owner_role=role.role_id,
            topic="Specialist review",
            action=role.reason,
            blocking=False,
            linked_questions=[],
            linked_findings=list(role.linked_findings),
        ))
        step += 1

    return nodes


def _biomarker_data(biomarker_id: str, entities: dict) -> dict:
    return (entities.get(biomarker_id, {}).get("data") or {}) if entities else {}


def _biomarker_label(biomarker_id: str, entities: dict) -> str:
    data = _biomarker_data(biomarker_id, entities)
    names = data.get("names") or {}
    return names.get("preferred") or biomarker_id


def _biomarker_owner_role(biomarker_id: str, entities: dict) -> str:
    data = _biomarker_data(biomarker_id, entities)
    biomarker_type = data.get("biomarker_type") or ""
    return _BIOMARKER_OWNER_BY_TYPE.get(biomarker_type, "medical_oncologist")


def _biomarker_candidate_fields(biomarker_id: str, entities: dict) -> list[str]:
    """Return likely patient-profile keys for a BIO-* requirement.

    Patient fixtures are not fully normalized yet: some use `BIO-*`, some
    use gene symbols, and some use clinical field names like
    `cd20_ihc_status`. This intentionally broad matcher is for data-quality
    display only; it never changes treatment selection.
    """
    data = _biomarker_data(biomarker_id, entities)
    candidates: list[str] = [biomarker_id]
    stripped = biomarker_id[4:] if biomarker_id.upper().startswith("BIO-") else biomarker_id
    candidates.extend([stripped, stripped.lower(), stripped.lower().replace("-", "_")])
    norm = stripped.lower().replace("-", "_")
    candidates.extend([f"{norm}_status", f"{norm}_result"])
    candidates.extend(_BIOMARKER_FIELD_ALIASES.get(biomarker_id, ()))

    mutation = data.get("mutation_details") or {}
    external = data.get("external_ids") or {}
    lookup = data.get("actionability_lookup") or {}
    for v in (
        mutation.get("gene"),
        external.get("hgnc_symbol"),
        lookup.get("gene"),
    ):
        if isinstance(v, str) and v.strip():
            candidates.extend([v.strip(), v.strip().lower()])

    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if not isinstance(c, str) or not c.strip():
            continue
        key = c.strip()
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(key)
    return out


def _has_biomarker_value(
    findings: dict[str, Any],
    biomarker_id: str,
    entities: dict,
) -> tuple[bool, Optional[str]]:
    for key in _biomarker_candidate_fields(biomarker_id, entities):
        if _has(findings, key):
            return True, key
    return False, None


def _collect_biomarker_coverage(
    plan_result: PlanResult,
    findings: dict[str, Any],
    entities: dict,
) -> dict:
    """Summarize treatment-track biomarker requirements for MDT review.

    This is a data-quality object, not a selection input. It reports which
    required biomarkers are known/missing and which track(s) depend on them.
    """
    requirements: dict[str, dict] = {}
    if not plan_result.plan:
        return {
            "required_total": 0,
            "required_known": 0,
            "required_missing": 0,
            "known": [],
            "missing": [],
        }

    for track in plan_result.plan.tracks:
        indication = track.indication_data or {}
        applicable = indication.get("applicable_to") or {}
        for req in applicable.get("biomarker_requirements_required") or []:
            biomarker_id = _biomarker_id_from_requirement(req)
            if not biomarker_id:
                continue
            entry = requirements.setdefault(
                biomarker_id,
                {
                    "biomarker_id": biomarker_id,
                    "label": _biomarker_label(biomarker_id, entities),
                    "value_constraint": _biomarker_requirement_constraint(req),
                    "owner_role": _biomarker_owner_role(biomarker_id, entities),
                    "tracks": [],
                    "default_track": False,
                    "known": False,
                    "matched_field": None,
                },
            )
            if not entry.get("value_constraint"):
                entry["value_constraint"] = _biomarker_requirement_constraint(req)
            track_ref = track.indication_id or indication.get("id") or track.label or "track"
            if track_ref not in entry["tracks"]:
                entry["tracks"].append(track_ref)
            if track.is_default:
                entry["default_track"] = True

    for entry in requirements.values():
        known, matched = _has_biomarker_value(findings, entry["biomarker_id"], entities)
        entry["known"] = known
        entry["matched_field"] = matched

    known_entries = sorted(
        (e for e in requirements.values() if e["known"]),
        key=lambda e: e["biomarker_id"],
    )
    missing_entries = sorted(
        (e for e in requirements.values() if not e["known"]),
        key=lambda e: (not e.get("default_track"), e["biomarker_id"]),
    )
    total = len(requirements)
    known_count = len(known_entries)
    pct = round((known_count / total) * 100) if total else 100
    return {
        "required_total": total,
        "required_known": known_count,
        "required_missing": len(missing_entries),
        "coverage_percent": pct,
        "known": known_entries,
        "missing": missing_entries,
    }


def _is_lymphoma(disease: Optional[dict]) -> bool:
    if not disease:
        return False
    lineage = (disease.get("lineage") or "").lower()
    if "lymphoma" in lineage:
        return True
    morph = (disease.get("codes") or {}).get("icd_o_3_morphology") or ""
    # ICD-O-3 morphology 9590-9729 / 9760-9769 = mature B/T-cell lymphomas
    if morph and len(morph) >= 4 and morph[:4].isdigit():
        n = int(morph[:4])
        if 9590 <= n <= 9729 or 9760 <= n <= 9769:
            return True
    return False


def _is_extranodal_malt(disease: Optional[dict]) -> bool:
    if not disease:
        return False
    morph = (disease.get("codes") or {}).get("icd_o_3_morphology") or ""
    return morph.startswith("9699")  # extranodal MZL of MALT type


# ── Role catalog (UA labels, no clinical content) ─────────────────────────


_ROLE_CATALOG: dict[str, str] = {
    "hematologist": "Гематолог / онкогематолог",
    "medical_oncologist": "Медичний онколог (хіміотерапевт солідних пухлин)",
    "infectious_disease_hepatology": "Інфекціоніст / гепатолог",
    "radiologist": "Лікар-радіолог",
    "pathologist": "Патолог (загальний)",
    "hematopathologist": "Гематопатолог (специфічно для лімфом / лейкозів / мієломи)",
    "molecular_geneticist": "Молекулярний генетик / молекулярний онколог",
    "clinical_pharmacist": "Клінічний фармацевт",
    "radiation_oncologist": "Радіотерапевт (променева терапія)",
    "surgical_oncologist": "Хірург-онколог",
    "transplant_specialist": "Спеціаліст з трансплантації (BMT)",
    "cellular_therapy_specialist": "Спеціаліст з клітинної терапії (CAR-T)",
    "psychologist": "Психолог / онкопсихолог",
    "palliative_care": "Паліативна допомога",
    "social_worker_case_manager": "Соціальний працівник / кейс-менеджер",
    "primary_care": "Сімейний лікар / терапевт",
}


# Biomarker types that warrant molecular-genetics expertise. Viral loads,
# CBC-derived markers, and basic IHC do NOT trigger — those stay in
# pathologist / infectious-disease scope.
_ACTIONABLE_GENOMIC_TYPES = {
    "gene_mutation",
    "fusion",
    "gene_fusion",
    "amplification",
    "deletion",
    "copy_number",
    "msi_status",
    "tmb",
    "methylation",
}

_BIOMARKER_OWNER_BY_TYPE = {
    "gene_mutation": "molecular_geneticist",
    "fusion": "molecular_geneticist",
    "gene_fusion": "molecular_geneticist",
    "amplification": "molecular_geneticist",
    "deletion": "molecular_geneticist",
    "copy_number": "molecular_geneticist",
    "msi_status": "molecular_geneticist",
    "tmb": "molecular_geneticist",
    "methylation": "molecular_geneticist",
    "protein_expression_ihc": "pathologist",
    "protein_serology": "infectious_disease_hepatology",
    "viral_load": "infectious_disease_hepatology",
    "tumor_marker": "medical_oncologist",
    "imaging": "radiologist",
}

_BIOMARKER_FIELD_ALIASES = {
    "BIO-BCL2-EXPRESSION-IHC": ("bcl2", "bcl2_ihc", "bcl2_expression"),
    "BIO-CD79B-IHC": ("cd79b", "cd79b_ihc"),
    "BIO-CD20-IHC": ("cd20_ihc_status", "cd20_ihc", "cd20"),
    "BIO-CD5-IHC": ("cd5_ihc_status", "cd5_ihc", "cd5"),
    "BIO-CD23-IHC": ("cd23_ihc_status", "cd23_ihc", "cd23"),
    "BIO-CD30-IHC": ("cd30_ihc_status", "cd30_ihc", "cd30"),
    "BIO-CCND1-IHC": ("ccnd1_ihc_status", "ccnd1_ihc", "cyclin_d1_ihc", "cyclin_d1"),
    "BIO-CD52-IHC": ("cd52_ihc_status", "cd52_ihc", "cd52"),
    "BIO-DLBCL-COO-HANS": ("cell_of_origin_hans", "cell_of_origin"),
    "BIO-DLBCL-IPI": ("ipi_score", "ipi", "international_prognostic_index"),
    "BIO-FL-FLIPI": ("flipi", "flipi_score"),
    "BIO-HBV-STATUS": ("hbsag", "anti_hbc_total", "hbv_status"),
    "BIO-HCV-STATUS": ("hcv_status", "hcv_known_positive", "anti_hcv"),
    "BIO-HIV-STATUS": ("hiv", "hiv_status", "hiv_serology"),
    "BIO-HTLV-1": ("htlv1_serology", "htlv_1_status", "htlv1_status"),
    "BIO-HCV-RNA": ("hcv_rna_positive", "hcv_rna_status", "hcv_rna"),
    "BIO-EBV-DNA": ("ebv_dna", "ebv_dna_status", "ebv_viral_load"),
    "BIO-HRD-STATUS": ("hrd_status", "hrd", "genomic_instability_score"),
    "BIO-HER2-SOLID": ("her2_status", "her2_ihc", "erbb2_status"),
    "BIO-BRAF-V600E": ("braf_v600e", "braf_status"),
    "BIO-MCL-MIPI": ("mipi_risk_group", "mipi", "mipi_score"),
    "BIO-T11-14-IGH-CCND1": (
        "t_11_14",
        "t11_14",
        "igh_ccnd1",
        "ccnd1_rearrangement",
        "t_11_14_igh_ccnd1",
    ),
    "BIO-NOTCH1-MUTATION": ("notch1_mutation", "notch1"),
    "BIO-PSA": ("psa", "psa_ng_ml"),
    "BIO-PD-L1": ("pdl1", "pd_l1", "pdl1_tps", "pd_l1_tps"),
    "BIO-PDL1-TPS": ("pdl1", "pd_l1", "pdl1_tps", "pd_l1_tps", "pdl1_tps_22c3"),
    "BIO-ALK-FUSION": ("alk_fusion", "alk_rearrangement", "alk_status"),
    "BIO-EGFR-MUTATION": ("egfr_mutation", "egfr_status"),
    "BIO-KRAS-G12C": ("kras_g12c", "kras_status"),
    "BIO-MET": ("met_ex14_skipping", "met_status"),
    "BIO-MET-AMPLIFICATION": ("met_amplification", "met_amp", "met_copy_number_gain"),
    "BIO-NTRK-FUSION": ("ntrk_fusion", "ntrk_status"),
    "BIO-RET": ("ret_fusion", "ret_status"),
    "BIO-ROS1-FUSION": ("ros1_fusion", "ros1_rearrangement", "ros1_status"),
}


def _role_name(role_id: str) -> str:
    return _ROLE_CATALOG.get(role_id, role_id)


# ── Skill registry (version + last_reviewed + clinical_lead per role) ─────
#
# Each MDT role is a "skill" — a versioned bundle of rules. As of skill
# candidate #7a (clinical sign-off 2026-04-26) the metadata for each
# skill lives in `knowledge_base/hosted/content/mdt_skills/<role_id>.yaml`
# rather than as a Python literal here, so clinical co-leads can bump
# version, add sign-offs, and register sources via the same two-reviewer
# governance as Indications and RedFlags (CHARTER §6.1, ADR-0002).
#
# The `_SKILL_REGISTRY` symbol is preserved (tests + render layer import
# it directly) but is now populated from the KB at module import time.
# The loader cache (validation/loader.py) makes the import-time read
# cheap — one cold parse per worker process, then pure dict access.
#
# Bump version when: rule semantics change (major), rule added/modified
# (minor), source citation or wording (patch). Update last_reviewed on
# every bump. Do this in the YAML, not here.

def _build_skill_registry() -> dict[str, SkillMetadata]:
    """Walk the loaded KB and project every `mdt_skills` entity into a
    `SkillMetadata` dataclass keyed on role_id. Called once at module
    import; tests that need a different KB call this manually after
    `clear_load_cache()`."""
    from knowledge_base.validation.loader import load_content

    kb_default = Path(__file__).resolve().parent.parent / "hosted" / "content"
    out: dict[str, SkillMetadata] = {}
    load = load_content(kb_default)
    for _eid, info in load.entities_by_id.items():
        if info["type"] != "mdt_skills":
            continue
        d = info["data"]
        role_id = d["role_id"]
        out[role_id] = SkillMetadata(
            skill_id=role_id,
            name=d["name"],
            version=d.get("version", "0.1.0"),
            last_reviewed=d.get("last_reviewed", ""),
            clinical_lead=d.get("clinical_lead"),
            verified_by=list(d.get("verified_by") or []),
            sources=list(d.get("sources") or []),
            domain=d.get("domain"),
            notes=d.get("notes"),
        )
    return out


_SKILL_REGISTRY: dict[str, SkillMetadata] = _build_skill_registry()


def get_skill(role_id: str) -> SkillMetadata:
    """Return registry entry for a role_id, or a synthetic 'unknown' record."""
    s = _SKILL_REGISTRY.get(role_id)
    if s is not None:
        return s
    return SkillMetadata(
        skill_id=role_id,
        name=_role_name(role_id),
        version="0.0.0",
        last_reviewed="unknown",
        notes="No skill metadata registered — add to _SKILL_REGISTRY.",
    )


# Maps a fired RedFlag id (or substring) → the role whose priority should
# escalate when that RedFlag fires with clinical_direction in {intensify, hold}.
# MVP scope; extend as KB grows.
_REDFLAG_DOMAIN_ROLE: dict[str, str] = {
    "RF-BULKY-DISEASE": "radiologist",
    "RF-AGGRESSIVE-HISTOLOGY-TRANSFORMATION": "pathologist",
    "RF-HBV-COINFECTION": "infectious_disease_hepatology",
    "RF-DECOMP-CIRRHOSIS": "infectious_disease_hepatology",
}

_ESCALATING_DIRECTIONS = {"intensify", "hold"}


def _collect_fired_red_flags(plan_result: PlanResult) -> list[str]:
    """Pull deduplicated fired-RedFlag IDs from the plan's algorithm trace
    (populated by algorithm_eval.walk_algorithm)."""
    if not plan_result.plan or not plan_result.plan.trace:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in plan_result.plan.trace:
        for rf in entry.get("fired_red_flags") or []:
            if rf not in seen:
                out.append(rf)
                seen.add(rf)
    return out


# ── Rule application ──────────────────────────────────────────────────────


def _apply_role_rules(
    patient: dict,
    plan_result: PlanResult,
    findings: dict[str, Any],
    disease_data: Optional[dict],
    entities: dict,
) -> list[MDTRequiredRole]:
    roles: dict[str, MDTRequiredRole] = {}

    def add(role_id: str, reason: str, trigger_type: TriggerType,
            priority: Priority, linked_findings: Optional[list[str]] = None) -> None:
        existing = roles.get(role_id)
        if existing is None:
            roles[role_id] = MDTRequiredRole(
                role_id=role_id,
                role_name=_role_name(role_id),
                reason=reason,
                trigger_type=trigger_type,
                priority=priority,
                linked_findings=list(linked_findings or []),
                skill=get_skill(role_id),
            )
            return
        # Dedupe — keep highest-priority + accumulate linked findings + extend reason if new
        if _PRIORITY_RANK[priority] > _PRIORITY_RANK[existing.priority]:
            existing.priority = priority
        for lf in linked_findings or []:
            if lf not in existing.linked_findings:
                existing.linked_findings.append(lf)

    plan = plan_result.plan
    tracks = plan.tracks if plan else []

    # R1 — lymphoma diagnosis → hematologist required
    if _is_lymphoma(disease_data):
        add(
            "hematologist",
            "Лімфомний діагноз — провідна спеціальність для терапевтичного ведення.",
            "diagnosis_complexity",
            "required",
            linked_findings=[plan_result.disease_id] if plan_result.disease_id else [],
        )

    # R2 — HCV/HBV positive → infectious disease / hepatology
    hcv_pos = (
        _truthy(findings, "BIO-HCV-RNA")
        or _truthy(findings, "hcv_rna_positive")
        or _truthy(findings, "hcv_rna_status")
    )
    hbv_pos = _truthy(findings, "hbsag") or _truthy(findings, "anti_hbc_total")
    if hcv_pos or hbv_pos:
        linked: list[str] = []
        if hcv_pos:
            linked.append("BIO-HCV-RNA")
        if hbv_pos:
            linked.append("HBV-serology")
        add(
            "infectious_disease_hepatology",
            "Активна вірусна етіологія (HCV/HBV) потребує паралельного ведення антивірусної терапії та оцінки реактивації.",
            "molecular_data",
            "recommended",
            linked_findings=linked,
        )

    # R3 — imaging fields present → radiologist (priority may escalate via RedFlag below)
    has_imaging = _has(
        findings,
        "dominant_nodal_mass_cm",
        "mediastinal_ratio",
        "pet_ct_date",
        "ct_findings",
        "lugano_stage",
    )
    if has_imaging:
        add(
            "radiologist",
            "Наявні візуалізаційні знахідки — потрібен радіолог для staging/restaging.",
            "diagnosis_complexity",
            "recommended",
            linked_findings=["imaging"],
        )

    # R4 — lymphoma OR pathology fields → pathologist
    pathology_fields_present = _has(
        findings,
        "biopsy_shows_dlbcl",
        "cd20_ihc_status",
        "ki67_percent",
        "biopsy_site",
    )
    if _is_lymphoma(disease_data) or pathology_fields_present:
        add(
            "pathologist",
            "Підтвердження гістології лімфоми + оцінка ризику трансформації (DLBCL/Richter).",
            "diagnosis_complexity",
            "recommended",
            linked_findings=["histology"],
        )

    # R5 — aggressive plan_track present → clinical pharmacist
    has_aggressive = any(
        (t.indication_data or {}).get("plan_track") == "aggressive" for t in tracks
    )
    if has_aggressive:
        add(
            "clinical_pharmacist",
            "Хіміоімунотерапевтичний схема — drug-drug interactions, dose adjustments, premedication.",
            "treatment_domain",
            "recommended",
            linked_findings=["aggressive-track"],
        )

    # R6 — extranodal MALT → radiation oncologist optional
    if _is_extranodal_malt(disease_data):
        add(
            "radiation_oncologist",
            "Екстранодальна MALT-лімфома — у частини локалізацій локальна променева терапія є опцією.",
            "treatment_domain",
            "optional",
            linked_findings=[plan_result.disease_id] if plan_result.disease_id else [],
        )

    # R7 — any regimen with non-reimbursed drug → social worker / case manager
    non_reimbursed_drugs: list[str] = []
    for t in tracks:
        regimen = t.regimen_data or {}
        per_component = (regimen.get("ukraine_availability") or {}).get("per_component") or {}
        for drug_id, info in per_component.items():
            if isinstance(info, dict) and info.get("reimbursed_nszu") is False:
                non_reimbursed_drugs.append(drug_id)
        # Also check Drug entity directly via component refs
        for comp in regimen.get("components") or []:
            drug_id = comp.get("drug_id")
            if not drug_id:
                continue
            drug = entities.get(drug_id, {}).get("data") if isinstance(entities, dict) else None
            ua = ((drug or {}).get("regulatory_status") or {}).get("ukraine_registration") or {}
            if ua.get("registered") and ua.get("reimbursed_nszu") is False:
                non_reimbursed_drugs.append(drug_id)
    if non_reimbursed_drugs:
        add(
            "social_worker_case_manager",
            "У плані використовуються препарати без реімбурсації НСЗУ — потрібна оцінка доступу для пацієнта.",
            "local_availability",
            "recommended",
            linked_findings=sorted(set(non_reimbursed_drugs)),
        )

    # R9 — actionable genomic biomarker required → molecular geneticist
    actionable_biomarkers: list[str] = []
    for t in tracks:
        applicable = (t.indication_data or {}).get("applicable_to") or {}
        for req in applicable.get("biomarker_requirements_required") or []:
            bm_id = req.get("biomarker_id") if isinstance(req, dict) else None
            if not bm_id:
                continue
            bm = entities.get(bm_id, {}).get("data") if isinstance(entities, dict) else None
            bm_type = (bm or {}).get("biomarker_type") or ""
            if bm_type in _ACTIONABLE_GENOMIC_TYPES:
                actionable_biomarkers.append(bm_id)
    if actionable_biomarkers:
        add(
            "molecular_geneticist",
            "Indication посилається на actionable геномний біомаркер — потрібна інтерпретація мутації / target / actionability.",
            "molecular_data",
            "recommended",
            linked_findings=sorted(set(actionable_biomarkers)),
        )

    # R8 — palliative care for poor performance status / decompensation
    try:
        ecog = int(findings.get("ecog") or 0)
    except (TypeError, ValueError):
        ecog = 0
    if ecog >= 3 or _truthy(findings, "decompensated_cirrhosis"):
        add(
            "palliative_care",
            "Знижений performance status / декомпенсована коморбідність — потрібна оцінка цілей лікування.",
            "palliative_need",
            "recommended",
            linked_findings=["ecog/decomp"],
        )

    # Priority escalation per spec §3: fired RedFlag with clinical_direction
    # in {intensify, hold} → role mapped via _REDFLAG_DOMAIN_ROLE escalates
    # to `required`.
    fired = _collect_fired_red_flags(plan_result)
    for rf_id in fired:
        rf_data = entities.get(rf_id, {}).get("data") if isinstance(entities, dict) else None
        if not rf_data:
            continue
        direction = (rf_data.get("clinical_direction") or "").strip().lower()
        if direction not in _ESCALATING_DIRECTIONS:
            continue
        escalated_role = _REDFLAG_DOMAIN_ROLE.get(rf_id)
        if not escalated_role or escalated_role not in roles:
            continue
        existing = roles[escalated_role]
        if _PRIORITY_RANK["required"] > _PRIORITY_RANK[existing.priority]:
            existing.priority = "required"
            existing.reason = (
                f"{existing.reason} Ескальовано через RedFlag {rf_id} "
                f"(clinical_direction={direction})."
            )
            if rf_id not in existing.linked_findings:
                existing.linked_findings.append(rf_id)

    return list(roles.values())


def _apply_open_question_rules(
    patient: dict,
    plan_result: PlanResult,
    findings: dict[str, Any],
    disease_data: Optional[dict],
    entities: dict,
) -> list[OpenQuestion]:
    questions: list[OpenQuestion] = []

    is_lymphoma = _is_lymphoma(disease_data)
    hcv_pos = (
        _truthy(findings, "BIO-HCV-RNA")
        or _truthy(findings, "hcv_rna_positive")
        or _truthy(findings, "hcv_rna_status")
    )
    aggressive_in_plan = any(
        (t.indication_data or {}).get("plan_track") == "aggressive"
        for t in (plan_result.plan.tracks if plan_result.plan else [])
    )
    has_anti_cd20_candidate = aggressive_in_plan or is_lymphoma

    # Q1 — HBV serology missing in any HCV/lymphoma patient considering anti-CD20
    if has_anti_cd20_candidate and not _has(findings, "hbsag", "anti_hbc_total"):
        questions.append(OpenQuestion(
            id="OQ-HBV-SEROLOGY",
            question=(
                "Чи проведена серологія HBV (HBsAg, anti-HBc total)? "
                "До початку anti-CD20 терапії статус має бути відомий."
            ),
            owner_role="infectious_disease_hepatology",
            blocking=True,
            rationale=(
                "Anti-CD20 без HBV профілактики при HBsAg+/anti-HBc+ "
                "несе значний ризик реактивації (CI-HBV-NO-PROPHYLAXIS)."
            ),
            linked_findings=["hbsag", "anti_hbc_total"],
        ))

    # Q2 — Hepatic fibrosis / Child-Pugh / FIB-4 missing for HCV+
    if hcv_pos and not _has(findings, "child_pugh_class", "decompensated_cirrhosis", "fib4_index"):
        questions.append(OpenQuestion(
            id="OQ-FIBROSIS-STAGE",
            question=(
                "Який стадій фіброзу/цирозу печінки (Child-Pugh, FIB-4)? "
                "Це впливає на вибір DAA та dosing бендамустину."
            ),
            owner_role="infectious_disease_hepatology",
            blocking=True,
            rationale=(
                "Декомпенсований цироз — RF-DECOMP-CIRRHOSIS, "
                "вимагає змін у схемі."
            ),
            linked_findings=["child_pugh_class", "fib4_index"],
        ))

    # Q3 — CD20 status missing for lymphoma diagnosis
    if is_lymphoma and not _has(findings, "cd20_ihc_status", "biopsy_confirmed"):
        questions.append(OpenQuestion(
            id="OQ-CD20-CONFIRMATION",
            question=(
                "Чи підтверджено CD20+ статус гістологією (IHC)? "
                "Без CD20+ rituximab/obinutuzumab не показані."
            ),
            owner_role="pathologist",
            blocking=True,
            rationale=(
                "Anti-CD20 терапія — основа для більшості ліній; "
                "відсутність експресії CD20 повністю змінює regimen."
            ),
            linked_findings=["cd20_ihc_status"],
        ))

    # Q4 — staging fields missing
    if is_lymphoma and not _has(findings, "lugano_stage", "pet_ct_date", "ct_findings"):
        questions.append(OpenQuestion(
            id="OQ-STAGING-COMPLETE",
            question=(
                "Чи виконано повне стадіювання (Lugano + PET/CT або CT)?"
            ),
            owner_role="radiologist",
            blocking=False,
            rationale="Прогноз і вибір треку залежать від stage та tumor burden.",
            linked_findings=["lugano_stage", "pet_ct_date"],
        ))

    # Q5 — aggressive track + missing LDH
    if aggressive_in_plan and not _has(findings, "ldh_ratio_to_uln", "ldh"):
        questions.append(OpenQuestion(
            id="OQ-LDH-CURRENT",
            question="Який актуальний LDH? Маркер пухлинного навантаження і трансформації.",
            owner_role="hematologist",
            blocking=False,
            rationale="LDH входить у прогностичні індекси індолентних лімфом.",
            linked_findings=["ldh_ratio_to_uln"],
        ))

    # Q6 — any track has a regimen that includes a non-reimbursed drug
    non_reimbursed: list[str] = []
    for t in (plan_result.plan.tracks if plan_result.plan else []):
        regimen = t.regimen_data or {}
        per_component = (regimen.get("ukraine_availability") or {}).get("per_component") or {}
        for drug_id, info in per_component.items():
            if isinstance(info, dict) and info.get("reimbursed_nszu") is False:
                non_reimbursed.append(drug_id)
    if non_reimbursed:
        questions.append(OpenQuestion(
            id="OQ-DRUG-AVAILABILITY",
            question=(
                "Чи доступні препарати без реімбурсації НСЗУ для пацієнта "
                f"({', '.join(sorted(set(non_reimbursed)))})? "
                "Чи потрібна social work consult / альтернативний схема?"
            ),
            owner_role="social_worker_case_manager",
            blocking=False,
            rationale=(
                "Препарати з reimbursed_nszu=false означають out-of-pocket "
                "вартість для пацієнта; це впливає на adherence та реалістичність плану."
            ),
            linked_findings=sorted(set(non_reimbursed)),
        ))

    # Q7 - any selected/alternative track requires a biomarker absent from
    # the patient profile. Default-track gaps are blocking; alternative-track
    # gaps are non-blocking but still assigned to the MDT owner.
    existing_question_ids = {q.id for q in questions}
    coverage = _collect_biomarker_coverage(plan_result, findings, entities)
    for missing in coverage.get("missing") or []:
        biomarker_id = missing["biomarker_id"]
        qid = "OQ-BIOMARKER-" + "".join(
            ch if ch.isalnum() else "-" for ch in biomarker_id.replace("BIO-", "")
        ).strip("-").upper()
        if qid in existing_question_ids:
            continue
        owner = missing.get("owner_role") or "medical_oncologist"
        label = missing.get("label") or biomarker_id
        tracks = ", ".join(missing.get("tracks") or [])
        constraint = missing.get("value_constraint")
        constraint_txt = f" Expected value: {constraint}." if constraint else ""
        is_blocking = bool(missing.get("default_track"))
        questions.append(OpenQuestion(
            id=qid,
            question=(
                f"What is the status of {label} ({biomarker_id})? "
                f"It is required by track(s): {tracks}.{constraint_txt}"
            ),
            owner_role=owner,
            blocking=is_blocking,
            rationale=(
                "A treatment-track biomarker requirement is missing from the "
                "patient profile; the MDT should verify the test result, method, "
                "specimen, and date before relying on this option."
            ),
            linked_findings=[biomarker_id],
        ))
        existing_question_ids.add(qid)

    return questions


# ── Data quality summary ──────────────────────────────────────────────────


_CRITICAL_FIELDS_LYMPHOMA = (
    "cd20_ihc_status",
    "hbsag",
    "anti_hbc_total",
    "lugano_stage",
)
_RECOMMENDED_FIELDS_LYMPHOMA = (
    "ldh_ratio_to_uln",
    "fib4_index",
    "ecog",
    "pet_ct_date",
)

_DATA_QUALITY_FIELD_DETAILS = {
    "cd20_ihc_status": {
        "label": "CD20 IHC status",
        "label_uk": "Статус CD20 за ІГХ",
        "owner_role": "pathologist",
        "why_it_matters": "Confirms CD20-directed therapy is biologically appropriate.",
        "why_it_matters_uk": "Підтверджує, що CD20-спрямована терапія біологічно обгрунтована.",
        "doctor_action": "Verify CD20 IHC result, specimen, method, and report date.",
        "doctor_action_uk": "Перевірити результат CD20 ІГХ, матеріал, метод і дату звіту.",
    },
    "hbsag": {
        "label": "HBsAg",
        "label_uk": "HBsAg",
        "owner_role": "infectious_disease_hepatology",
        "why_it_matters": "Identifies active HBV infection and prophylaxis need before anti-CD20 or other immunosuppressive therapy.",
        "why_it_matters_uk": "Виявляє активну HBV-інфекцію та потребу в профілактиці перед anti-CD20 або іншою імуносупресивною терапією.",
        "doctor_action": "Order or document HBsAg before treatment start.",
        "doctor_action_uk": "Призначити або задокументувати HBsAg до початку лікування.",
    },
    "anti_hbc_total": {
        "label": "Total anti-HBc",
        "label_uk": "anti-HBc total",
        "owner_role": "infectious_disease_hepatology",
        "why_it_matters": "Detects prior HBV exposure and reactivation risk.",
        "why_it_matters_uk": "Виявляє перенесений контакт з HBV і ризик реактивації.",
        "doctor_action": "Order or document total anti-HBc and decide prophylaxis/monitoring.",
        "doctor_action_uk": "Призначити або задокументувати anti-HBc total і визначити профілактику/моніторинг.",
    },
    "lugano_stage": {
        "label": "Lugano stage",
        "label_uk": "Стадія Lugano",
        "owner_role": "radiologist",
        "why_it_matters": "Defines lymphoma extent and supports tumor-burden and response-assessment decisions.",
        "why_it_matters_uk": "Визначає поширеність лімфоми та підтримує оцінку пухлинного навантаження і відповіді.",
        "doctor_action": "Document Lugano stage from PET/CT or contrast CT staging.",
        "doctor_action_uk": "Задокументувати стадію Lugano за PET/CT або контрастним CT.",
    },
    "ldh_ratio_to_uln": {
        "label": "LDH ratio to ULN",
        "label_uk": "LDH відносно ВМН",
        "owner_role": "medical_oncologist",
        "why_it_matters": "Supports prognostic scoring and aggressive-biology flags.",
        "why_it_matters_uk": "Потрібно для прогностичних індексів і прапорців агресивної біології.",
        "doctor_action": "Enter LDH with local upper limit of normal.",
        "doctor_action_uk": "Внести LDH разом із локальною верхньою межею норми.",
    },
    "fib4_index": {
        "label": "FIB-4 liver fibrosis index",
        "label_uk": "Індекс фіброзу печінки FIB-4",
        "owner_role": "infectious_disease_hepatology",
        "why_it_matters": "Screens hepatic fibrosis risk before hepatotoxic therapy or antiviral coordination.",
        "why_it_matters_uk": "Скринінгує ризик фіброзу печінки перед гепатотоксичною терапією або координацією противірусного лікування.",
        "doctor_action": "Calculate FIB-4 from age, AST, ALT, and platelet count.",
        "doctor_action_uk": "Розрахувати FIB-4 за віком, AST, ALT і кількістю тромбоцитів.",
    },
    "ecog": {
        "label": "ECOG performance status",
        "label_uk": "Функціональний статус ECOG",
        "owner_role": "medical_oncologist",
        "why_it_matters": "Constrains treatment intensity and eligibility for intensive regimens.",
        "why_it_matters_uk": "Обмежує інтенсивність лікування та придатність до інтенсивних режимів.",
        "doctor_action": "Record ECOG PS assessed at treatment decision visit.",
        "doctor_action_uk": "Задокументувати ECOG PS на візиті прийняття рішення щодо лікування.",
    },
    "pet_ct_date": {
        "label": "PET/CT date",
        "label_uk": "Дата PET/CT",
        "owner_role": "radiologist",
        "why_it_matters": "Shows whether baseline staging is recent enough for treatment planning and later response comparison.",
        "why_it_matters_uk": "Показує, чи базове стадіювання достатньо актуальне для планування лікування і подальшого порівняння відповіді.",
        "doctor_action": "Document baseline PET/CT date or explain alternative staging modality.",
        "doctor_action_uk": "Задокументувати дату базового PET/CT або пояснити альтернативний метод стадіювання.",
    },
}


def _missing_field_detail(
    field: str,
    severity: Literal["critical", "recommended"],
    field_unlocks: dict[str, list[str]],
) -> dict:
    meta = _DATA_QUALITY_FIELD_DETAILS.get(field, {})
    return {
        "field": field,
        "label": meta.get("label") or field,
        "label_uk": meta.get("label_uk") or meta.get("label") or field,
        "severity": severity,
        "owner_role": meta.get("owner_role") or "medical_oncologist",
        "why_it_matters": meta.get("why_it_matters") or (
            "Required for complete MDT review of this plan."
        ),
        "why_it_matters_uk": meta.get("why_it_matters_uk") or (
            "Потрібно для повного розгляду цього плану на MDT."
        ),
        "doctor_action": meta.get("doctor_action") or f"Verify and document {field}.",
        "doctor_action_uk": meta.get("doctor_action_uk") or f"Перевірити та задокументувати {field}.",
        "blocked_red_flags": list(field_unlocks.get(field) or []),
    }


def _trigger_referenced_fields(trigger: Any) -> list[str]:
    """Walk a RedFlag.trigger dict (any/all/none_of-style) and collect every
    `finding` / `condition` / `lab` / `symptom` key referenced. Used to
    detect RedFlags whose required inputs are absent from patient findings."""
    if not isinstance(trigger, dict):
        return []
    out: list[str] = []
    for key in ("finding", "condition", "lab", "symptom"):
        v = trigger.get(key)
        if isinstance(v, str) and v:
            out.append(v)
    for nested_key in ("all_of", "any_of", "none_of"):
        for sub in trigger.get(nested_key) or []:
            out.extend(_trigger_referenced_fields(sub))
    return out


def _unevaluated_red_flags(
    findings: dict[str, Any],
    disease_data: Optional[dict],
    entities: dict,
) -> list[str]:
    """RedFlag IDs whose trigger references at least one finding key absent
    from the patient profile, AND whose `relevant_diseases` list either
    includes the patient's disease_id or is unspecified (global RedFlag).

    Empty list when no RedFlags can be evaluated incompletely."""
    out: list[str] = []
    disease_id = (disease_data or {}).get("id")
    for eid, info in (entities or {}).items():
        if info.get("type") != "redflags":
            continue
        rf = info.get("data") or {}
        relevant = rf.get("relevant_diseases") or []
        if relevant and disease_id and disease_id not in relevant:
            continue
        refs = _trigger_referenced_fields(rf.get("trigger") or {})
        if not refs:
            continue
        # If ANY referenced field is absent, RedFlag couldn't be fully evaluated
        if any(not _has(findings, f) for f in refs):
            out.append(eid)
    return sorted(out)


def _field_unlocks_map(
    missing_fields: list[str],
    disease_data: Optional[dict],
    entities: dict,
) -> dict[str, list[str]]:
    """Return {field: [rf_id, ...]} for each missing field that is referenced
    by at least one relevant RedFlag trigger. Used to cross-link the 'missing'
    and 'unevaluated' sections so a clinician sees why a field matters."""
    if not missing_fields or not entities:
        return {}
    disease_id = (disease_data or {}).get("id")
    result: dict[str, list[str]] = {f: [] for f in missing_fields}
    for eid, info in entities.items():
        if info.get("type") != "redflags":
            continue
        rf = info.get("data") or {}
        relevant = rf.get("relevant_diseases") or []
        if relevant and disease_id and disease_id not in relevant:
            continue
        refs = set(_trigger_referenced_fields(rf.get("trigger") or {}))
        for field in missing_fields:
            if field in refs:
                result[field].append(eid)
    return {f: sorted(rfs) for f, rfs in result.items() if rfs}


def _data_quality(
    findings: dict[str, Any],
    disease_data: Optional[dict],
    entities: dict,
    plan_result: Optional[PlanResult] = None,
) -> dict:
    is_lymphoma = _is_lymphoma(disease_data)
    critical = list(_CRITICAL_FIELDS_LYMPHOMA) if is_lymphoma else []
    recommended = list(_RECOMMENDED_FIELDS_LYMPHOMA) if is_lymphoma else []

    missing_critical = [f for f in critical if not _has(findings, f)]
    missing_recommended = [f for f in recommended if not _has(findings, f)]
    unevaluated = _unevaluated_red_flags(findings, disease_data, entities)
    field_unlocks = _field_unlocks_map(
        missing_critical + missing_recommended, disease_data, entities
    )
    biomarker_coverage = (
        _collect_biomarker_coverage(plan_result, findings, entities)
        if plan_result is not None
        else {}
    )
    missing_default_biomarkers = sum(
        1 for item in biomarker_coverage.get("missing", [])
        if item.get("default_track")
    )
    missing_field_details = [
        *[
            _missing_field_detail(field, "critical", field_unlocks)
            for field in missing_critical
        ],
        *[
            _missing_field_detail(field, "recommended", field_unlocks)
            for field in missing_recommended
        ],
    ]
    if missing_default_biomarkers:
        status = "incomplete_for_default_track"
        doctor_summary = (
            "Default-track review is incomplete until required biomarker gaps "
            "are resolved."
        )
    elif missing_critical:
        status = "incomplete_for_mdt_review"
        doctor_summary = (
            "MDT sign-off is incomplete until critical clinical data gaps are "
            "resolved."
        )
    elif missing_recommended or unevaluated or biomarker_coverage.get("required_missing", 0):
        status = "usable_with_caveats"
        doctor_summary = (
            "No critical default-track gap was found, but the MDT should "
            "review the listed caveats before final sign-off."
        )
    else:
        status = "complete_for_mdt_review"
        doctor_summary = (
            "Required MDT data checks are complete for the current case profile."
        )

    return {
        "status": status,
        "doctor_summary": doctor_summary,
        "missing_critical_fields": missing_critical,
        "missing_recommended_fields": missing_recommended,
        "missing_field_details": missing_field_details,
        "ambiguous_findings": [],
        "unevaluated_red_flags": unevaluated,
        "field_unlocks": field_unlocks,
        "biomarker_coverage": biomarker_coverage,
        "missing_default_biomarkers": missing_default_biomarkers,
        "fields_present_count": sum(1 for v in findings.values() if v not in (None, "")),
        "fields_expected_count": len(critical) + len(recommended),
    }


# ── Aggregation summary ───────────────────────────────────────────────────


# Live-API clients available in knowledge_base/clients/. Listed by source_id;
# this is what the engine *would* call during evaluation. Used in
# aggregation_summary so the MDT brief shows step 2 ("AI-агрегація")
# explicitly per the project infographic.
_KNOWN_LIVE_API_CLIENTS = (
    "SRC-CTGOV-REGISTRY",
    "SRC-PUBMED",
    "SRC-DAILYMED",
    "SRC-OPENFDA",
)


def _build_aggregation_summary(
    plan_result: PlanResult,
    entities: dict,
    questions: list[OpenQuestion],
    fired_red_flags: list[str],
) -> dict:
    """Make the implicit "AI-агрегація" step explicit per the project
    infographic. Counters describe what the engine pulled together for
    this run — surface for HCP transparency, not for clinical reasoning."""

    plan = plan_result.plan
    cited_sources: set[str] = set()
    indications_evaluated = 0
    biomarker_refs: set[str] = set()

    if plan:
        for t in plan.tracks:
            indications_evaluated += 1
            ind = t.indication_data or {}
            for s in ind.get("sources") or []:
                if isinstance(s, dict) and s.get("source_id"):
                    cited_sources.add(s["source_id"])
                elif isinstance(s, str):
                    cited_sources.add(s)
            applicable = ind.get("applicable_to") or {}
            for req in applicable.get("biomarker_requirements_required") or []:
                if isinstance(req, dict) and req.get("biomarker_id"):
                    biomarker_refs.add(req["biomarker_id"])

    rf_count = sum(1 for info in (entities or {}).values() if info.get("type") == "redflags")

    return {
        "kb_entities_loaded": len(entities or {}),
        "kb_sources_cited": sorted(cited_sources),
        "indications_evaluated": indications_evaluated,
        "biomarkers_referenced": sorted(biomarker_refs),
        "red_flags_total_in_kb": rf_count,
        "red_flags_fired": list(fired_red_flags),
        "open_questions_raised": len(questions),
        "live_api_clients_available": list(_KNOWN_LIVE_API_CLIENTS),
        "live_api_clients_invoked": [],  # MVP: clients not auto-invoked yet
    }


# ── Provenance bootstrap ──────────────────────────────────────────────────


def _bootstrap_provenance(
    plan_result: PlanResult,
    required_roles: list[MDTRequiredRole],
    recommended_roles: list[MDTRequiredRole],
    optional_roles: list[MDTRequiredRole],
    open_questions: list[OpenQuestion],
) -> DecisionProvenanceGraph:
    plan = plan_result.plan
    plan_id = (plan.id if plan else "PLAN-UNKNOWN")
    plan_version = (plan.version if plan else 1)

    graph = DecisionProvenanceGraph(plan_version=plan_version)

    if plan_result.disease_id:
        graph.add_node(plan_result.disease_id, "diagnosis", plan_result.disease_id)
    for t in (plan.tracks if plan else []):
        if t.indication_id:
            graph.add_node(t.indication_id, "plan_section", t.label or t.indication_id)
            if plan_result.disease_id:
                graph.add_edge(plan_result.disease_id, t.indication_id, "candidate")

    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"EV-{plan_id}-{counter:03d}"

    # Engine plan-generation event
    graph.add_event(make_event(
        event_id=next_id(),
        actor_role="engine",
        event_type="confirmed",
        target_type="plan_section",
        target_id=plan_id,
        summary=f"Engine згенерував план {plan_id} (версія {plan_version}).",
    ))

    # Per-role role-request events
    for role in (*required_roles, *recommended_roles, *optional_roles):
        graph.add_event(make_event(
            event_id=next_id(),
            actor_role="engine",
            event_type="requested_data",
            target_type="plan_section",
            target_id=role.role_id,
            summary=f"Запрошено роль '{role.role_name}' (priority={role.priority}): {role.reason}",
        ))

    # Per-question events
    for q in open_questions:
        graph.add_event(make_event(
            event_id=next_id(),
            actor_role="engine",
            event_type="added_question",
            target_type="plan_section",
            target_id=q.id,
            summary=f"Підняте питання для {q.owner_role} (blocking={q.blocking}): {q.question}",
        ))

    # Per-fired-RedFlag events (one event per RedFlag, deduplicated across steps).
    # `plan.algorithm_id` is Optional (KSS §20.2): treatment plans always carry
    # an ALGO-* id, but PreventionPlan output (RF-driven routing, no Algorithm
    # walked) sets it to None. Substitute a human-readable fallback so the
    # summary never reads "алгоритму None." for prevention-path plans.
    if plan and plan.trace:
        algo_label = (
            plan.algorithm_id
            if plan.algorithm_id
            else "профілактичного маршруту"
        )
        seen_rfs: set[str] = set()
        for entry in plan.trace:
            for rf_id in entry.get("fired_red_flags") or []:
                if rf_id in seen_rfs:
                    continue
                seen_rfs.add(rf_id)
                graph.add_event(make_event(
                    event_id=next_id(),
                    actor_role="engine",
                    event_type="flagged_risk",
                    target_type="red_flag",
                    target_id=rf_id,
                    summary=(
                        f"RedFlag {rf_id} спрацював на step {entry.get('step')} "
                        f"алгоритму {algo_label}."
                    ),
                ))

    return graph


# ── Diagnostic-mode rules (D1-D6 / DQ1-DQ4) ──────────────────────────────


def _apply_diagnostic_role_rules(
    patient: dict,
    diag_result: "DiagnosticPlanResult",
    findings: dict[str, Any],
) -> list[MDTRequiredRole]:
    """D1-D6 from specs/DIAGNOSTIC_MDT_SPEC.md §4. Operates on the
    suspicion shape, NOT on Indications/regimens (we have neither yet)."""

    suspicion = diag_result.suspicion
    if suspicion is None:
        return []

    roles: dict[str, MDTRequiredRole] = {}

    def add(role_id: str, reason: str, trigger_type: TriggerType,
            priority: Priority, linked_findings: Optional[list[str]] = None) -> None:
        existing = roles.get(role_id)
        if existing is None:
            roles[role_id] = MDTRequiredRole(
                role_id=role_id,
                role_name=_role_name(role_id),
                reason=reason,
                trigger_type=trigger_type,
                priority=priority,
                linked_findings=list(linked_findings or []),
                skill=get_skill(role_id),
            )
            return
        if _PRIORITY_RANK[priority] > _PRIORITY_RANK[existing.priority]:
            existing.priority = priority

    lineage = (suspicion.lineage_hint or "").lower()
    is_lymph_suspect = "lymphoma" in lineage or lineage in {"mzl", "lymph"}
    is_solid_suspect = any(t in lineage for t in ("solid_tumor", "carcinoma", "sarcoma", "melanoma"))

    # D1 — lymphoma suspicion → hematologist required
    if is_lymph_suspect:
        add(
            "hematologist",
            "Підозра на лімфому — провідна спеціальність для diagnostic workup та подальшого ведення.",
            "diagnosis_complexity",
            "required",
            linked_findings=["suspicion.lineage_hint"],
        )

    # D2 — any suspicion → biopsy → pathologist required
    add(
        "pathologist",
        "Будь-яка підозра вимагає біопсії — патолог планує вибір місця, IHC панель, ancillary tests.",
        "diagnosis_complexity",
        "required",
        linked_findings=["suspicion"],
    )

    # D3 — tissue locations OR imaging fields present → radiologist required
    if suspicion.tissue_locations or _has(
        findings, "dominant_nodal_mass_cm", "splenic_mass_cm", "mediastinal_ratio",
        "pet_ct_date", "ct_findings", "lugano_stage",
    ):
        add(
            "radiologist",
            "Stage / restaging imaging + biopsy guidance — радіолог.",
            "diagnosis_complexity",
            "required",
            linked_findings=list(suspicion.tissue_locations) or ["imaging"],
        )

    # D4 — solid-tumor suspicion → surgical oncologist (resectability, biopsy approach)
    if is_solid_suspect:
        add(
            "surgical_oncologist",
            "Підозра на солідну пухлину — оцінка resectability, biopsy approach.",
            "treatment_domain",
            "recommended",
            linked_findings=["suspicion.lineage_hint"],
        )

    # D5 — lymphoma suspicion + HCV/HBV unresolved → infectious disease
    history = patient.get("history") or {}
    hcv_known = history.get("hcv_known_positive")
    hbv_known = history.get("hbv_known_positive")
    if is_lymph_suspect and (hcv_known is None or hbv_known is None):
        add(
            "infectious_disease_hepatology",
            "Перед anti-CD20 treatment status HCV/HBV має бути відомий — ще на діагностичній фазі.",
            "molecular_data",
            "recommended",
            linked_findings=["history.hcv_known_positive", "history.hbv_known_positive"],
        )

    # D6 — poor performance / decompensation → palliative for early goals-of-care
    try:
        ecog = int(findings.get("ecog") or 0)
    except (TypeError, ValueError):
        ecog = 0
    presentation = (suspicion.presentation or "").lower()
    if ecog >= 3 or "decompens" in presentation:
        add(
            "palliative_care",
            "Знижений performance status / ознаки декомпенсації — рання оцінка цілей лікування.",
            "palliative_need",
            "recommended",
            linked_findings=["ecog/presentation"],
        )

    return list(roles.values())


def _apply_diagnostic_open_questions(
    patient: dict,
    diag_result: "DiagnosticPlanResult",
    findings: dict[str, Any],
) -> list[OpenQuestion]:
    """DQ1-DQ4 from specs/DIAGNOSTIC_MDT_SPEC.md §5."""

    suspicion = diag_result.suspicion
    if suspicion is None:
        return []

    questions: list[OpenQuestion] = []
    lineage = (suspicion.lineage_hint or "").lower()
    is_lymph = "lymphoma" in lineage or lineage in {"mzl", "lymph"}

    # DQ1 — lymphoma suspect AND CD20 status absent
    if is_lymph and not _has(findings, "cd20_ihc_status"):
        questions.append(OpenQuestion(
            id="DQ-CD20-AFTER-BIOPSY",
            question="Який результат CD20 IHC буде після біопсії? Без CD20+ rituximab/obinutuzumab не показані.",
            owner_role="pathologist",
            blocking=True,
            rationale="Базис для будь-якого anti-CD20-containing regimen у майбутньому.",
            linked_findings=["cd20_ihc_status"],
        ))

    # DQ2 — lymphoma suspect AND HBV serology absent
    if is_lymph and not _has(findings, "hbsag", "anti_hbc_total"):
        questions.append(OpenQuestion(
            id="DQ-HBV-SEROLOGY-EARLY",
            question="Серологія HBV (HBsAg, anti-HBc) — обов'язкова перед anti-CD20; почати workup зараз.",
            owner_role="infectious_disease_hepatology",
            blocking=True,
            rationale="HBV reactivation risk при anti-CD20 без prophylaxis.",
            linked_findings=["hbsag", "anti_hbc_total"],
        ))

    # DQ3 — lymphoma suspect AND staging fields absent
    if is_lymph and not _has(findings, "lugano_stage", "pet_ct_date"):
        questions.append(OpenQuestion(
            id="DQ-STAGING-PLAN",
            question="Чи запланований повний staging (PET/CT + bone marrow за показаннями)?",
            owner_role="radiologist",
            blocking=True,
            rationale="Stage визначає track і treatment intensity.",
            linked_findings=["lugano_stage", "pet_ct_date"],
        ))

    # DQ4 — multiple working_hypotheses → differential plan needed
    if len(suspicion.working_hypotheses) >= 2:
        hyps = ", ".join(suspicion.working_hypotheses)
        questions.append(OpenQuestion(
            id="DQ-DIFFERENTIAL",
            question=(
                f"Який план диференціальної діагностики між гіпотезами: {hyps}? "
                "Які молекулярні / IHC тести розрізняють?"
            ),
            owner_role="pathologist",
            blocking=False,
            rationale="Множинні гіпотези — розрізнити їх перед treatment discussion.",
            linked_findings=list(suspicion.working_hypotheses),
        ))

    return questions


# ── Public entry point ────────────────────────────────────────────────────


def orchestrate_mdt(
    patient: dict,
    plan_or_diagnostic,
    kb_root: Path | str = "knowledge_base/hosted/content",
) -> MDTOrchestrationResult:
    """Build an MDT brief for either a treatment PlanResult OR a
    DiagnosticPlanResult. Mode is detected by the type of the second
    argument.

    Important: read-only with respect to the input. Callers can rely on
    `plan_result.default_indication_id` being unchanged after this call
    (asserted in tests).
    """

    # Lazy import to avoid a circular dependency at module-load time
    from .diagnostic import DiagnosticPlanResult

    if isinstance(plan_or_diagnostic, DiagnosticPlanResult):
        return _orchestrate_mdt_diagnostic(patient, plan_or_diagnostic, kb_root)

    plan_result: PlanResult = plan_or_diagnostic
    findings = _flatten_findings(patient)

    load = load_content(Path(kb_root))
    entities = load.entities_by_id
    warnings: list[str] = []
    for path, msg in load.schema_errors:
        warnings.append(f"schema error in {path.name}: {msg[:120]}")
    for path, msg in load.ref_errors:
        warnings.append(f"ref error in {path.name}: {msg}")

    disease_data = (
        entities.get(plan_result.disease_id, {}).get("data")
        if plan_result.disease_id
        else None
    )

    roles = _apply_role_rules(patient, plan_result, findings, disease_data, entities)
    questions = _apply_open_question_rules(patient, plan_result, findings, disease_data, entities)
    quality = _data_quality(findings, disease_data, entities, plan_result)
    fired = _collect_fired_red_flags(plan_result)
    aggregation = _build_aggregation_summary(plan_result, entities, questions, fired)

    # Cross-link: roles that own questions get question IDs in linked_questions
    roles_by_id = {r.role_id: r for r in roles}
    for q in questions:
        owner = roles_by_id.get(q.owner_role)
        if owner is not None and q.id not in owner.linked_questions:
            owner.linked_questions.append(q.id)

    required = sorted(
        [r for r in roles if r.priority == "required"], key=lambda r: r.role_id
    )
    recommended = sorted(
        [r for r in roles if r.priority == "recommended"], key=lambda r: r.role_id
    )
    optional = sorted(
        [r for r in roles if r.priority == "optional"], key=lambda r: r.role_id
    )
    talk_tree = _build_talk_tree(required, recommended, optional, questions)

    provenance = _bootstrap_provenance(plan_result, required, recommended, optional, questions)

    # Rehydrate persisted reviewer events for this patient (CHARTER §6).
    # Without this merge, every fresh orchestration would lose historical
    # `confirmed` / `modified` / `approved` events. Silent if no events
    # file exists yet.
    # Resolve DEFAULT_ROOT through the module attribute (not the captured
    # function default) so tests can monkeypatch event_store.DEFAULT_ROOT.
    try:
        from . import event_store as _evstore
        if plan_result.patient_id:
            _evstore.merge_events_into_graph(
                provenance, plan_result.patient_id, root=_evstore.DEFAULT_ROOT
            )
    except Exception as exc:  # noqa: BLE001 — never fail orchestration on event rehydration
        warnings.append(f"event-store rehydration failed: {exc}")

    return MDTOrchestrationResult(
        patient_id=plan_result.patient_id,
        plan_id=(plan_result.plan.id if plan_result.plan else None),
        disease_id=plan_result.disease_id,
        required_roles=required,
        recommended_roles=recommended,
        optional_roles=optional,
        open_questions=questions,
        talk_tree=talk_tree,
        data_quality_summary=quality,
        aggregation_summary=aggregation,
        warnings=warnings,
        provenance=provenance,
    )


def _orchestrate_mdt_diagnostic(
    patient: dict,
    diag_result,
    kb_root: Path | str,
) -> MDTOrchestrationResult:
    """MDT brief for diagnostic-mode (pre-histology) workflow.

    Applies D1-D6 / DQ1-DQ4. Does NOT use treatment-mode rules — there
    are no Indications, no regimens, no biomarker-requirements yet.
    """

    from .diagnostic import DiagnosticPlanResult  # for type hint only

    findings = _flatten_findings(patient)
    load = load_content(Path(kb_root))
    entities = load.entities_by_id
    warnings: list[str] = []
    for path, msg in load.schema_errors:
        warnings.append(f"schema error in {path.name}: {msg[:120]}")
    for path, msg in load.ref_errors:
        warnings.append(f"ref error in {path.name}: {msg}")

    roles = _apply_diagnostic_role_rules(patient, diag_result, findings)
    questions = _apply_diagnostic_open_questions(patient, diag_result, findings)

    # Cross-link
    roles_by_id = {r.role_id: r for r in roles}
    for q in questions:
        owner = roles_by_id.get(q.owner_role)
        if owner is not None and q.id not in owner.linked_questions:
            owner.linked_questions.append(q.id)

    required = sorted([r for r in roles if r.priority == "required"], key=lambda r: r.role_id)
    recommended = sorted([r for r in roles if r.priority == "recommended"], key=lambda r: r.role_id)
    optional = sorted([r for r in roles if r.priority == "optional"], key=lambda r: r.role_id)
    talk_tree = _build_talk_tree(required, recommended, optional, questions)

    # Diagnostic data quality: missing critical fields list mirrors what
    # DQ1-DQ3 actually test for + a couple of demographic essentials.
    is_lymph = "lymphoma" in (diag_result.suspicion.lineage_hint or "").lower() if diag_result.suspicion else False
    critical_fields = ("hbsag", "anti_hbc_total", "cd20_ihc_status", "lugano_stage") if is_lymph else ()
    quality = {
        "missing_critical_fields": [f for f in critical_fields if not _has(findings, f)],
        "missing_recommended_fields": [],
        "ambiguous_findings": [],
        "unevaluated_red_flags": [],
        "fields_present_count": sum(1 for v in findings.values() if v not in (None, "")),
        "fields_expected_count": len(critical_fields),
    }

    # Aggregation summary — diagnostic-mode flavour
    aggregation = {
        "mode": "diagnostic",
        "kb_entities_loaded": len(entities),
        "matched_workup_id": diag_result.matched_workup_id,
        "workup_steps": (
            len(diag_result.diagnostic_plan.workup_steps)
            if diag_result.diagnostic_plan
            else 0
        ),
        "mandatory_questions": (
            len(diag_result.diagnostic_plan.mandatory_questions)
            if diag_result.diagnostic_plan
            else 0
        ),
        "open_questions_raised": len(questions),
        "live_api_clients_available": list(_KNOWN_LIVE_API_CLIENTS),
        "live_api_clients_invoked": [],
    }

    # Diagnostic-mode provenance: simpler — no fired_red_flags etc.
    plan_id = (diag_result.diagnostic_plan.id if diag_result.diagnostic_plan else "DPLAN-UNKNOWN")
    plan_version = (diag_result.diagnostic_plan.version if diag_result.diagnostic_plan else 1)
    graph = DecisionProvenanceGraph(plan_version=plan_version)

    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"EV-{plan_id}-{counter:03d}"

    graph.add_event(make_event(
        event_id=next_id(),
        actor_role="engine",
        event_type="confirmed",
        target_type="plan_section",
        target_id=plan_id,
        summary=f"Engine згенерував diagnostic brief {plan_id} (версія {plan_version}).",
    ))
    for role in (*required, *recommended, *optional):
        graph.add_event(make_event(
            event_id=next_id(),
            actor_role="engine",
            event_type="requested_data",
            target_type="plan_section",
            target_id=role.role_id,
            summary=f"Запрошено роль '{role.role_name}' (priority={role.priority}): {role.reason}",
        ))
    for q in questions:
        graph.add_event(make_event(
            event_id=next_id(),
            actor_role="engine",
            event_type="added_question",
            target_type="plan_section",
            target_id=q.id,
            summary=f"Підняте питання для {q.owner_role} (blocking={q.blocking}): {q.question}",
        ))

    return MDTOrchestrationResult(
        patient_id=diag_result.patient_id,
        plan_id=plan_id,
        disease_id=None,  # by definition
        required_roles=required,
        recommended_roles=recommended,
        optional_roles=optional,
        open_questions=questions,
        talk_tree=talk_tree,
        data_quality_summary=quality,
        aggregation_summary=aggregation,
        warnings=warnings + list(diag_result.warnings),
        provenance=graph,
    )


__all__ = [
    "MDTOrchestrationResult",
    "MDTRequiredRole",
    "MDTTalkTreeNode",
    "OpenQuestion",
    "orchestrate_mdt",
]
