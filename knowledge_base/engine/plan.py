"""Top-level plan generation.

    patient profile  →  Disease match  →  applicable Algorithm
                                    →   Algorithm walked with RedFlags
                                    →   Plan with multiple tracks (≥2)
                                    →   one rendered document per CHARTER §2

Per CHARTER §2 the output always presents at least two alternative tracks
in **one document**. The data-model guarantee for this comes from
`Algorithm.output_indications` (≥2 candidates) plus `default_indication`
+ `alternative_indication` markers.

FDA non-device CDS positioning (CHARTER §15) requires every Plan to surface
the four Criterion-4 elements (intended use, HCP user, patient population,
algorithm summary, data limitations). Engine populates these from Algorithm
and Indication metadata.

Patient profile shape (dict; MVP — we will move to FHIR/mCODE later):

    {
        "patient_id": "PZ-001",                      # required for Plan persistence
        "disease": {"icd_o_3_morphology": "9699/3"}, # or {"id": "DIS-HCV-MZL"}
        "line_of_therapy": 1,                        # default 1
        "biomarkers": {"BIO-HCV-RNA": "positive"},
        "demographics": {"age": 58, "ecog": 1, ...},
        "findings": {"dominant_nodal_mass_cm": 4.0, ...},
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from knowledge_base.schemas import (
    AccessMatrix,
    AccessMatrixRow,
    ExperimentalOption,
    FDAComplianceMetadata,
    Plan,
    PlanTrack,
    VariantActionabilityHit,
)
from knowledge_base.validation.loader import load_content
from ._actionability import find_matching_actionability
from ._track_filter import is_track_excluded
from .access_matrix import build_access_matrix
from .algorithm_eval import walk_algorithm
from .experimental_options import SearchFn, enumerate_experimental_options
from .actionability_types import ActionabilityLayer
from .redflag_eval import evaluate_redflag_trigger


# Track labels — ordered, default labels for the well-known plan_track values.
# Extend as we add new track types (palliative, trial-only, etc.)
_TRACK_LABELS_UA = {
    "standard": "Стандартний план",
    "aggressive": "Агресивний план",
    "surveillance": "Активне спостереження (watch-and-wait)",
    "palliative": "Паліативний план",
    "trial": "План у рамках клінічного дослідження",
    "local_therapy": "Локальна терапія",
    "transplant": "Трансплантаційний план",
}
_TRACK_LABELS_EN = {
    "standard": "Standard plan",
    "aggressive": "Aggressive plan",
    "surveillance": "Active surveillance (watch-and-wait)",
    "palliative": "Palliative plan",
    "trial": "Clinical-trial-only plan",
    "local_therapy": "Local therapy plan",
    "transplant": "Transplant plan",
}


@dataclass
class PlanResult:
    """In-memory engine output. Carries both the new Plan structure and
    backward-compat fields for existing tests.
    """

    # Core
    patient_id: Optional[str]
    disease_id: Optional[str]
    algorithm_id: Optional[str]

    # New primary structure: full Plan with tracks + FDA metadata
    plan: Optional[Plan] = None

    # Back-compat shortcuts (derived from plan.tracks)
    default_indication_id: Optional[str] = None
    alternative_indication_id: Optional[str] = None
    default_indication: Optional[dict] = None
    alternative_indication: Optional[dict] = None

    # Engine internals
    trace: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Render-time-only metadata: open clinical trials matching this
    # disease + biomarker + line scenario. NEVER read by the engine as
    # a selection signal (CHARTER §8.3, plan §3.2 invariant). When no
    # search function is wired, this stays None — render shows the
    # "ctgov sync needed" placeholder per plan §3.3.
    experimental_options: Optional[ExperimentalOption] = None

    # Actionability precision-medicine layer (safe-rollout v3 §0.1
    # invariant 1: surface-only, never influences track selection).
    # None when integration is disabled (default) or when the patient
    # has no actionable biomarkers. Render layer reads this in HCP mode
    # only; patient-mode HTML must NOT contain any actionability detail.
    # Renamed from `oncokb_layer` (CIViC pivot — see
    # docs/reviews/oncokb-public-civic-coverage-2026-04-27.md).
    actionability_layer: Optional[ActionabilityLayer] = None

    # Runtime KB resolutions for the render layer — NOT persisted with Plan.
    # Holds: 'disease' (dict), 'tests' (dict[id, dict]), 'red_flags' (dict[id, dict]),
    # 'algorithm' (dict). Populated by generate_plan; render gracefully degrades
    # if absent. Persistence (save_result) ignores this field entirely — the
    # rendered Plan dict is the source of truth on disk.
    kb_resolved: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "disease_id": self.disease_id,
            "algorithm_id": self.algorithm_id,
            "default_indication_id": self.default_indication_id,
            "alternative_indication_id": self.alternative_indication_id,
            "default_indication": self.default_indication,
            "alternative_indication": self.alternative_indication,
            "plan": self.plan.model_dump() if self.plan else None,
            "trace": self.trace,
            "warnings": self.warnings,
            "experimental_options": (
                self.experimental_options.model_dump()
                if self.experimental_options is not None
                else None
            ),
        }


# ── KB lookup helpers ─────────────────────────────────────────────────────────


def _find_disease_id(patient: dict, entities_by_id: dict) -> Optional[str]:
    dinfo = patient.get("disease") or {}
    if "id" in dinfo:
        return dinfo["id"]
    icd = dinfo.get("icd_o_3_morphology")
    if icd:
        for eid, info in entities_by_id.items():
            if info["type"] != "diseases":
                continue
            codes = info["data"].get("codes") or {}
            if codes.get("icd_o_3_morphology") == icd:
                return eid
    return None


def _find_algorithm(
    disease_id: str,
    line: int,
    entities_by_id: dict,
    disease_state: Optional[str] = None,
) -> Optional[dict]:
    """Find the algorithm matching disease + line, with optional disease_state
    disambiguation.

    When multiple algorithms exist for the same disease + line (e.g. prostate
    mHSPC vs mCRPC), the patient's `disease_state` selects the right one.
    Match priority: state-matched > state-agnostic. State-mismatched
    algorithms are never returned.
    """
    state_matched: list[dict] = []
    state_agnostic: list[dict] = []
    state_specific_any: list[dict] = []  # legacy fallback only
    patient_state = (disease_state or "").strip().lower() or None
    for info in entities_by_id.values():
        if info["type"] != "algorithms":
            continue
        d = info["data"]
        if d.get("applicable_to_disease") != disease_id:
            continue
        if d.get("applicable_to_line_of_therapy") != line:
            continue
        algo_state_raw = d.get("applicable_to_disease_state")
        if algo_state_raw is None:
            state_agnostic.append(d)
            continue
        state_specific_any.append(d)
        algo_state = str(algo_state_raw).strip().lower()
        if patient_state and algo_state == patient_state:
            state_matched.append(d)
        # else: state set on algorithm but does not match patient → skip
    if state_matched:
        return state_matched[0]
    if state_agnostic:
        return state_agnostic[0]
    # Legacy patient profile (no disease_state) and only state-specific
    # algorithms exist → load-order fallback to avoid breaking older cases.
    # The caller emits a warning so the gap is visible.
    if patient_state is None and state_specific_any:
        return state_specific_any[0]
    return None


def _collect_redflags(entities_by_id: dict) -> dict[str, dict]:
    return {eid: info["data"] for eid, info in entities_by_id.items() if info["type"] == "redflags"}


def _flatten_findings(patient: dict) -> dict:
    """Build the flat findings dict used by RF trigger evaluation.

    Composes patient.findings + patient.biomarkers + patient.demographics
    into a single dict. `setdefault` preserves explicit `findings` over
    biomarker / demographic name collisions. Used by both the treatment
    path (after algorithm resolution) and the prevention path (KSS §20.2
    — RF firing detection without a Disease).
    """
    findings = dict(patient.get("findings") or {})
    for k, v in (patient.get("biomarkers") or {}).items():
        findings.setdefault(k, v)
    for k, v in (patient.get("demographics") or {}).items():
        findings.setdefault(k, v)
    return findings


# ── §20 Prevention path (RATIFIED 2026-05-18) ────────────────────────────────
# When patient profile lacks a confirmed Disease but carries ≥1 fired
# prevention-eligible RedFlag (RedFlag.risk_category set), the engine
# routes to PreventionPlan generation instead of failing to plan. Tracks
# come from Indications with intent ∈ {prevention, screening, surveillance}
# whose applicable_to.disease_id matches the fired RF's relevant_diseases.
# CHARTER §15 C1 preserved: HCP user, patient-mode bundle = translation
# of the HCP-targeted plan, not a separate clinical product.


def _is_prevention_redflag(rf: dict) -> bool:
    """A RedFlag participates in the prevention path iff risk_category is
    set (KSS §20.1). Treatment-time RedFlags (risk_category unset) are
    invisible to PreventionPlan generation."""
    return bool(rf.get("risk_category"))


def _find_fired_prevention_rfs(
    findings: dict, redflag_lookup: dict[str, dict]
) -> list[dict]:
    """Return the list of prevention RedFlags whose trigger fires on the
    patient findings. Order preserved from KB iteration."""
    fired: list[dict] = []
    for rf in redflag_lookup.values():
        if not _is_prevention_redflag(rf):
            continue
        trigger = rf.get("trigger")
        if not isinstance(trigger, dict):
            continue
        if evaluate_redflag_trigger(trigger, findings):
            fired.append(rf)
    return fired


def _is_prevention_indication(ind: dict) -> bool:
    """Indication participates in PreventionPlan iff intent ∈
    {prevention, screening, surveillance}. The default `treatment` intent
    is invisible to PreventionPlan."""
    intent = ind.get("intent", "treatment")
    return intent in ("prevention", "screening", "surveillance")


def _find_prevention_indications(
    fired_rfs: list[dict],
    patient_biomarkers: dict,
    entities: dict,
) -> list[dict]:
    """Find prevention Indications matching at least one fired RF.

    Matching contract (KSS §20.2):
      - Indication.intent ∈ {prevention, screening, surveillance}
      - Indication.applicable_to.disease_id ∈ fired_rf.relevant_diseases
        for at least one fired RF
      - is_track_excluded returns False against patient biomarker profile

    Returns deduplicated Indication dicts in stable order (first-match
    by RF iteration). Engine downstream materializes one track per
    Indication.
    """
    relevant_disease_ids: set[str] = set()
    for rf in fired_rfs:
        for did in rf.get("relevant_diseases") or []:
            if did and did != "*":
                relevant_disease_ids.add(did)

    seen: set[str] = set()
    matched: list[dict] = []
    for eid, info in entities.items():
        if info["type"] != "indications":
            continue
        ind = info["data"]
        if not _is_prevention_indication(ind):
            continue
        applicable = ind.get("applicable_to") or {}
        ind_disease = applicable.get("disease_id")
        if ind_disease not in relevant_disease_ids:
            continue
        if eid in seen:
            continue
        if is_track_excluded(ind, patient_biomarkers):
            continue
        matched.append(ind)
        seen.add(eid)
    return matched


def _build_prevention_fda_compliance(
    fired_rfs: list[dict],
    tracks: list["PlanTrack"],
    entities: dict,
    warnings: list[str],
) -> "FDAComplianceMetadata":
    """Prevention-specific synthesizer for the four §15 Criterion-4 fields.

    Phrasing differs from the treatment-path synthesizer: intended use is
    prevention/screening counsel, the HCP user spec covers genetic
    counselor / primary-care MD / oncologist consultations, patient
    population is at-risk asymptomatic individuals, algorithm summary
    describes the RF-driven routing (no Algorithm walked).

    All §15 C1-C7 invariants preserved: HCP-only audience, ≥2 tracks
    (caller verifies), no time-critical Indications (per the RFs filtered
    in via risk_category), no raw image / signal input (CDS scope
    unchanged).
    """
    source_ids: set[str] = set()
    for t in tracks:
        ind = t.indication_data or {}
        for s in ind.get("sources") or []:
            if isinstance(s, dict) and s.get("source_id"):
                source_ids.add(s["source_id"])
            elif isinstance(s, str):
                source_ids.add(s)
    for rf in fired_rfs:
        for sid in rf.get("sources") or []:
            if isinstance(sid, str):
                source_ids.add(sid)

    sources_summary: list[str] = []
    for sid in sorted(source_ids):
        srec = _resolve(entities, sid)
        if srec:
            sources_summary.append(
                f"{sid}: {srec.get('title', '')} ({srec.get('version', '')})"
            )
        else:
            sources_summary.append(f"{sid}: (not in KB)")

    time_critical = any((t.indication_data or {}).get("time_critical") for t in tracks)

    rf_summary = ", ".join(rf.get("id", "?") for rf in fired_rfs) or "(none)"
    prevention_targets = sorted(
        {
            (t.indication_data or {}).get("applicable_to", {}).get("disease_id", "?")
            for t in tracks
        }
    )

    limitations: list[str] = list(warnings)
    if time_critical:
        limitations.append(
            "WARNING: Prevention plan includes time-critical Indications — "
            "falls OUTSIDE FDA non-device CDS carve-out per §520(o)(1)(E)."
        )
    if len(tracks) < 2:
        limitations.append(
            f"WARNING: PreventionPlan has only {len(tracks)} track(s) — "
            "CHARTER §15.2 C4 requires ≥2. Author additional prevention "
            "Indication(s) for the matched RF(s) before publishing."
        )

    return FDAComplianceMetadata(
        intended_use=(
            "HCP-mediated prevention / early-diagnosis counseling for "
            "at-risk asymptomatic individuals (CHARTER §3 amendment "
            "2026-05-18, Path A). Not a medical device; not for autonomous "
            "clinical decision-making; not for patient-direct deployment."
        ),
        hcp_user_specification=(
            "Licensed clinician (genetic counselor, primary-care physician, "
            "oncologist, or hematologist) conducting a risk-assessment "
            "consultation with the at-risk individual. Intended user must "
            "be qualified to independently review the basis of every "
            "recommendation and to order genetic tests / referrals where "
            "indicated."
        ),
        patient_population_match=(
            f"At-risk asymptomatic adult individuals with no current "
            f"diagnosis of the cancer(s) being targeted for prevention "
            f"({', '.join(prevention_targets) or '?'}). Eligibility "
            f"established via the fired prevention RedFlag(s): {rf_summary}."
        ),
        algorithm_summary=(
            "Rule-based prevention routing: patient findings evaluated "
            "against prevention-eligible RedFlag triggers (RedFlag."
            "risk_category set per KSS §20.1). Fired RFs route the patient "
            "to candidate prevention Indications whose applicable_to."
            "disease_id matches the RF's relevant_diseases. ≥2 tracks "
            "presented for HCP review (KSS §20.2)."
        ),
        data_sources_summary=sources_summary,
        data_limitations=limitations,
        automation_bias_warning=(
            "Both prevention options below are presented for review. The "
            "engine's selection of a 'recommended' default does not "
            "constitute a clinical decision. Final selection requires HCP "
            "judgment incorporating information not available to the "
            "system (patient values, prior conversations, access "
            "constraints, undocumented comorbidities)."
        ),
        time_critical=time_critical,
    )


def _try_generate_prevention_plan(
    patient: dict,
    entities: dict,
    redflag_lookup: dict[str, dict],
    result: "PlanResult",
    plan_version: int,
    supersedes: Optional[str],
    revision_trigger: Optional[str],
) -> bool:
    """Run the prevention path. Mutates `result` in place when ≥1 prevention
    RF fires and ≥1 prevention Indication matches. Returns True iff a
    PreventionPlan was built; False means caller falls through to the
    existing 'could not resolve disease' warning.

    §15 C4 ≥2-tracks invariant: when only one Indication matches, the
    PreventionPlan is still built but FDA compliance metadata carries an
    explicit limitation warning. Authoring TODO is for the clinical
    content side (add a second prevention Indication for that RF / disease
    bucket), not for the engine to synthesize.
    """
    findings = _flatten_findings(patient)
    fired_rfs = _find_fired_prevention_rfs(findings, redflag_lookup)
    if not fired_rfs:
        return False

    patient_biomarkers = patient.get("biomarkers") or {}
    matched_indications = _find_prevention_indications(
        fired_rfs, patient_biomarkers, entities
    )
    if not matched_indications:
        result.warnings.append(
            "prevention RFs fired ("
            + ", ".join(rf.get("id", "?") for rf in fired_rfs)
            + ") but no prevention Indications matched the patient profile"
        )
        return False

    tracks: list[PlanTrack] = []
    for i, ind in enumerate(matched_indications):
        track_label = ind.get("plan_track") or ind.get("id", "")
        is_default = i == 0
        reason = (
            "Recommended prevention pathway per fired RF(s): "
            + ", ".join(rf.get("id", "?") for rf in fired_rfs)
            if is_default
            else "Alternative prevention pathway presented for HCP consideration"
        )
        tracks.append(
            _materialize_track(track_label, ind["id"], is_default, reason, entities)
        )

    fda = _build_prevention_fda_compliance(
        fired_rfs, tracks, entities, result.warnings
    )

    rf_disease_targets = sorted(
        {
            (ind.get("applicable_to") or {}).get("disease_id")
            for ind in matched_indications
            if (ind.get("applicable_to") or {}).get("disease_id")
        }
    )
    kb_state = {
        "loaded_entities": len(entities),
        "indications_used": [t.indication_id for t in tracks],
        "sequencing_indications": [],
        "fired_prevention_redflags": [rf.get("id") for rf in fired_rfs],
        "prevention_targets": rf_disease_targets,
        "algorithm_version": None,  # no algorithm walked for prevention path
    }

    plan_id = (
        f"PLAN-{(result.patient_id or 'ANONYMOUS').upper()}-V{plan_version}"
    )
    result.plan = Plan(
        id=plan_id,
        patient_id=result.patient_id or "ANONYMOUS",
        version=plan_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        supersedes=supersedes,
        superseded_by=None,
        revision_trigger=revision_trigger,
        patient_snapshot=patient,
        algorithm_id=None,  # PreventionPlan: no algorithm
        knowledge_base_state=kb_state,
        tracks=tracks,
        sequencing_tracks=[],
        fda_compliance=fda,
        trace=[
            {
                "step": "prevention_rf_fired",
                "rf_id": rf.get("id"),
                "risk_category": rf.get("risk_category"),
                "clinical_direction": rf.get("clinical_direction"),
            }
            for rf in fired_rfs
        ],
        warnings=result.warnings,
        annotations=[],
    )

    # Back-compat shortcuts
    if tracks:
        result.default_indication_id = tracks[0].indication_id
        result.default_indication = tracks[0].indication_data
        if len(tracks) >= 2:
            result.alternative_indication_id = tracks[1].indication_id
            result.alternative_indication = tracks[1].indication_data

    # kb_resolved — disease is the prevention TARGET (the cancer being
    # prevented), pulled from the first matched indication. Render layer
    # uses this for the "prevention target" header.
    primary_target_id = (
        (matched_indications[0].get("applicable_to") or {}).get("disease_id")
        if matched_indications
        else None
    )
    test_ids: set[str] = set()
    redflag_ids: set[str] = {rf.get("id") for rf in fired_rfs if rf.get("id")}
    drug_ids: set[str] = set()
    for t in tracks:
        ind = t.indication_data or {}
        test_ids.update(ind.get("required_tests") or [])
        test_ids.update(ind.get("desired_tests") or [])
        reg = t.regimen_data or {}
        for comp in reg.get("components") or []:
            did = comp.get("drug_id") if isinstance(comp, dict) else None
            if did:
                drug_ids.add(did)
    result.kb_resolved = {
        "disease": _resolve(entities, primary_target_id) if primary_target_id else None,
        "algorithm": None,
        "tests": {tid: _resolve(entities, tid) for tid in test_ids if _resolve(entities, tid)},
        "red_flags": {rid: _resolve(entities, rid) for rid in redflag_ids if _resolve(entities, rid)},
        "drugs": {did: _resolve(entities, did) for did in drug_ids if _resolve(entities, did)},
    }

    return True


def _resolve(entities: dict, entity_id: Optional[str]) -> Optional[dict]:
    if entity_id and entity_id in entities:
        return entities[entity_id]["data"]
    return None


def _indication_line_of_therapy(indication: Optional[dict]) -> Optional[int]:
    applicable_to = (indication or {}).get("applicable_to") or {}
    value = applicable_to.get("line_of_therapy")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_current_line_indication(indication: Optional[dict], patient_line: int) -> bool:
    authored_line = _indication_line_of_therapy(indication)
    return authored_line is None or authored_line == patient_line


def _line_context_reason(indication: Optional[dict], patient_line: int) -> str:
    authored_line = _indication_line_of_therapy(indication)
    if authored_line is None:
        return "No authored line_of_therapy; retained for HCP review"
    if authored_line < patient_line:
        return (
            f"Prior-line candidate only: indication line {authored_line}, "
            f"patient line {patient_line}; not a current treatment option"
        )
    if authored_line > patient_line:
        return (
            f"Later-line sequencing candidate: indication line {authored_line}, "
            f"patient line {patient_line}; not a current treatment option"
        )
    return "Current-line treatment candidate"


def _compact_trace_note(note: Any, limit: int = 280) -> str:
    if not note:
        return ""
    text = " ".join(str(note).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _format_current_default_reason(
    algorithm: dict,
    trace: list[dict],
    selected_indication_id: Optional[str],
    default_indication_id: Optional[str],
) -> str:
    algo_id = algorithm.get("id", "algorithm")
    if not trace:
        return f"Primary current-line option from {algo_id}; no decision trace was recorded."

    last = trace[-1] or {}
    step = last.get("step")
    branch = last.get("branch") if isinstance(last.get("branch"), dict) else {}
    branch_result = branch.get("result") if branch else last.get("result")
    note = _compact_trace_note(branch.get("notes") or last.get("note"))
    fired = [str(x) for x in (last.get("fired_red_flags") or [])]
    winner = last.get("winner_red_flag")

    step_text = f"step {step}" if step is not None else "the fallback path"

    if selected_indication_id is None and branch_result is None:
        reason = (
            f"Provisional current-line default from {algo_id}: {step_text} "
            "did not select a treatment branch."
        )
        if note:
            reason += f" {note}"
        return reason

    if selected_indication_id == default_indication_id or branch_result == default_indication_id:
        if winner:
            return (
                f"Primary current-line option selected by {algo_id} at {step_text}; "
                f"branch-driving red flag: {winner}."
            )
        if fired:
            return (
                f"Primary current-line option selected by {algo_id} at {step_text}; "
                f"fired red flags: {', '.join(fired)}."
            )
        return f"Primary current-line option selected by {algo_id} at {step_text}."

    if selected_indication_id:
        if winner:
            return (
                f"Primary current-line option selected by {algo_id} at {step_text}; "
                f"branch-driving red flag: {winner}."
            )
        return f"Primary current-line option selected by {algo_id} at {step_text}."

    return f"Primary current-line option from {algo_id}; review decision trace for details."


# ── Track materialization ─────────────────────────────────────────────────────


def _materialize_track(
    track_id: str,
    indication_id: str,
    is_default: bool,
    selection_reason: str,
    entities: dict,
) -> PlanTrack:
    indication = _resolve(entities, indication_id)
    regimen = None
    monitoring = None
    supportive: list[dict] = []
    contras: list[dict] = []

    if indication:
        regimen = _resolve(entities, indication.get("recommended_regimen"))
        if regimen:
            monitoring = _resolve(entities, regimen.get("monitoring_schedule_id"))
            for sup_id in regimen.get("mandatory_supportive_care") or []:
                d = _resolve(entities, sup_id)
                if d:
                    supportive.append(d)
        for ci_id in indication.get("hard_contraindications") or []:
            d = _resolve(entities, ci_id)
            if d:
                contras.append(d)

    return PlanTrack(
        track_id=track_id,
        label=_TRACK_LABELS_UA.get(track_id, track_id),
        label_en=_TRACK_LABELS_EN.get(track_id, track_id),
        indication_id=indication_id,
        is_default=is_default,
        selection_reason=selection_reason,
        indication_data=indication,
        regimen_data=regimen,
        monitoring_data=monitoring,
        supportive_care_data=supportive,
        contraindications_data=contras,
    )


# ── FDA compliance metadata ───────────────────────────────────────────────────


def _build_fda_compliance(
    algorithm: dict,
    tracks: list[PlanTrack],
    entities: dict,
    warnings: list[str],
) -> FDAComplianceMetadata:
    """Populate the four Criterion-4 fields that every rendered Plan must carry.
    See specs/CHARTER.md §15 and the FDA Clinical Decision Support Guidance
    (specs/Guidance-Clinical-Decision-Software_5.pdf, source SRC-FDA-CDS-2026)."""

    # Aggregate sources cited across all tracks
    source_ids: set[str] = set()
    for t in tracks:
        ind = t.indication_data or {}
        for s in ind.get("sources") or []:
            if isinstance(s, dict) and s.get("source_id"):
                source_ids.add(s["source_id"])
            elif isinstance(s, str):
                source_ids.add(s)

    sources_summary: list[str] = []
    for sid in sorted(source_ids):
        srec = _resolve(entities, sid)
        if srec:
            sources_summary.append(f"{sid}: {srec.get('title', '')} ({srec.get('version', '')})")
        else:
            sources_summary.append(f"{sid}: (not in KB)")

    # Time-critical: any track marked time_critical disqualifies the whole plan
    time_critical = any((t.indication_data or {}).get("time_critical") for t in tracks)

    limitations: list[str] = list(warnings)
    if time_critical:
        limitations.append(
            "WARNING: This plan includes time-critical Indications — falls "
            "OUTSIDE FDA non-device CDS carve-out per §520(o)(1)(E) Criterion 4."
        )

    return FDAComplianceMetadata(
        intended_use=(
            "Outpatient oncology treatment planning to support tumor-board "
            "discussion. Not a medical device; not for autonomous clinical "
            "decision-making."
        ),
        hcp_user_specification=(
            "Licensed oncologist or hematologist participating in a "
            "multidisciplinary tumor board. Intended user must be qualified "
            "to independently review the basis of every recommendation."
        ),
        patient_population_match=(
            (
                f"Adults with confirmed {(tracks[0].indication_data or {}).get('applicable_to', {}).get('disease_id', 'disease')} "
                f"diagnosis at line of therapy "
                f"{(tracks[0].indication_data or {}).get('applicable_to', {}).get('line_of_therapy', '?')}."
            ) if tracks else "Adults with confirmed oncology diagnosis."
        ),
        algorithm_summary=algorithm.get("purpose") or (
            "Rule-based decision tree evaluating patient findings against "
            "RedFlag entities, selecting an Indication from a fixed candidate "
            "set authored by clinical reviewers."
        ),
        data_sources_summary=sources_summary,
        data_limitations=limitations,
        automation_bias_warning=(
            "Both treatment options below are presented for review. The "
            "engine's selection of a 'recommended' default does not constitute "
            "a clinical decision. Final treatment selection requires HCP "
            "judgment incorporating information not available to the system."
        ),
        time_critical=time_critical,
    )


# ── Top-level entry point ─────────────────────────────────────────────────────


def generate_plan(
    patient: dict,
    kb_root: Path | str = "knowledge_base/hosted/content",
    plan_version: int = 1,
    supersedes: Optional[str] = None,
    revision_trigger: Optional[str] = None,
    experimental_search_fn: Optional[SearchFn] = None,
    experimental_cache_root: Optional[Path | str] = None,
    actionability_enabled: bool = False,
    actionability_client: Optional[Any] = None,
) -> PlanResult:
    """Run the rule engine on a patient profile and return a PlanResult
    containing a fully-materialized Plan with multiple tracks.

    `experimental_search_fn`: optional ctgov search callable. When
    provided, `generate_plan` calls `enumerate_experimental_options`
    after track materialization and attaches the result as
    `result.experimental_options`. This is render-time metadata only —
    never a selection signal (CHARTER §8.3, plan §3.2 invariant).

    `experimental_cache_root`: optional directory holding cached
    `ExperimentalOption` JSONs (7-day TTL). Used in two modes:
    (a) with `experimental_search_fn`: cache-then-fetch (server-side
    builds, prewarm via `scripts/sync_ctgov_trials.py`); (b) without
    `experimental_search_fn`: cache-only (Pyodide demo, where the
    browser can't reach api.clinicaltrials.gov but the bundled cache
    can serve hits).
    """

    result = PlanResult(
        patient_id=patient.get("patient_id"),
        disease_id=None,
        algorithm_id=None,
    )

    load = load_content(Path(kb_root))
    if not load.ok:
        for path, msg in load.schema_errors:
            result.warnings.append(f"schema error in {path.name}: {msg[:120]}")
        for path, msg in load.ref_errors:
            result.warnings.append(f"ref error in {path.name}: {msg}")

    entities = load.entities_by_id
    disease_id = _find_disease_id(patient, entities)
    if disease_id is None:
        # §20 prevention path (RATIFIED 2026-05-18) — patient has no confirmed
        # Disease, but may carry ≥1 fired prevention-eligible RedFlag. Try
        # PreventionPlan generation before failing.
        prevention_redflags = _collect_redflags(entities)
        if _try_generate_prevention_plan(
            patient,
            entities,
            prevention_redflags,
            result,
            plan_version=plan_version,
            supersedes=supersedes,
            revision_trigger=revision_trigger,
        ):
            return result
        result.warnings.append("Could not resolve disease from patient.disease")
        return result
    result.disease_id = disease_id

    line = int(patient.get("line_of_therapy", 1))
    patient_disease_state = patient.get("disease_state") or (
        (patient.get("disease") or {}).get("state")
        if isinstance(patient.get("disease"), dict)
        else None
    )
    algo = _find_algorithm(disease_id, line, entities, disease_state=patient_disease_state)
    if algo is None:
        state_suffix = f", disease_state={patient_disease_state}" if patient_disease_state else ""
        result.warnings.append(
            f"No Algorithm found for disease={disease_id}, line_of_therapy={line}{state_suffix}"
        )
        return result
    if (
        patient_disease_state is None
        and algo.get("applicable_to_disease_state") is not None
    ):
        result.warnings.append(
            f"patient.disease_state is missing — fell back to {algo['id']} by load-order; "
            f"set disease_state explicitly to disambiguate (e.g. 'mHSPC' vs 'mCRPC')"
        )
    result.algorithm_id = algo["id"]

    # Flatten findings + biomarkers + demographics for clause evaluation
    findings = _flatten_findings(patient)

    # Hard gate: ECOG PS ≥ 4 — active treatment is clinically inappropriate.
    # Standard and aggressive tracks are suppressed; palliative/surveillance/trial
    # tracks pass through unchanged.
    try:
        _ecog_ps = int(findings.get("ecog") or 0)
    except (TypeError, ValueError):
        _ecog_ps = 0

    redflag_lookup = _collect_redflags(entities)
    selected, trace = walk_algorithm(algo, findings, redflag_lookup)
    result.trace = trace

    # Build the full track list — every Indication in algorithm.output_indications
    # becomes a track, ordered with the engine-selected default first.
    candidates = list(algo.get("output_indications") or [])
    default_id = selected or algo.get("default_indication")
    if default_id and default_id in candidates:
        candidates.remove(default_id)
        candidates.insert(0, default_id)

    current_candidate_ids: list[str] = []
    sequencing_candidate_ids: list[str] = []
    for ind_id in candidates:
        ind = _resolve(entities, ind_id)
        if _is_current_line_indication(ind, line):
            current_candidate_ids.append(ind_id)
        else:
            sequencing_candidate_ids.append(ind_id)

    selected_line = _indication_line_of_therapy(_resolve(entities, default_id))
    if selected_line is not None and selected_line != line:
        result.warnings.append(
            f"selected indication {default_id} authored for line {selected_line}; "
            f"patient is line {line}. Moved non-current candidate out of current tracks."
        )

    current_default_id = default_id if default_id in current_candidate_ids else None
    authored_default = algo.get("default_indication")
    if current_default_id is None and authored_default in current_candidate_ids:
        current_default_id = authored_default
    if current_default_id is None and current_candidate_ids:
        current_default_id = current_candidate_ids[0]
        result.warnings.append(
            f"no same-line selected/default indication for {algo['id']}; "
            f"using first current-line candidate {current_default_id}"
        )
    if current_default_id and current_default_id in current_candidate_ids:
        current_candidate_ids.remove(current_default_id)
        current_candidate_ids.insert(0, current_default_id)

    # Lenient biomarker-aware track filtering: drop only when the patient
    # profile EXPLICITLY violates an Indication's
    # `biomarker_requirements_excluded` list. Missing biomarkers do NOT
    # drop a track — see engine/_track_filter.py for rationale.
    patient_biomarkers = patient.get("biomarkers") or {}

    _ACTIVE_TRACKS = {"standard", "aggressive"}

    tracks: list[PlanTrack] = []
    for ind_id in current_candidate_ids:
        ind = _resolve(entities, ind_id)
        if ind and is_track_excluded(ind, patient_biomarkers):
            result.warnings.append(
                f"track {ind_id} dropped: patient biomarker profile "
                f"explicitly violates biomarker_requirements_excluded"
            )
            continue
        track_label = (ind or {}).get("plan_track") or ind_id
        if _ecog_ps >= 4 and track_label in _ACTIVE_TRACKS:
            result.warnings.append(
                f"track {ind_id} suppressed: ECOG {_ecog_ps} — "
                "active treatment not appropriate; palliative care only"
            )
            continue
        is_default = ind_id == current_default_id
        reason = (
            _format_current_default_reason(algo, trace, selected, current_default_id)
            if is_default
            else "Current-line alternative presented for HCP consideration"
        )
        tracks.append(_materialize_track(track_label, ind_id, is_default, reason, entities))

    sequencing_tracks: list[PlanTrack] = []
    for ind_id in sequencing_candidate_ids:
        ind = _resolve(entities, ind_id)
        if ind and is_track_excluded(ind, patient_biomarkers):
            continue
        track_label = (ind or {}).get("plan_track") or ind_id
        reason = _line_context_reason(ind, line)
        sequencing_tracks.append(
            _materialize_track(track_label, ind_id, False, reason, entities)
        )

    if tracks and not any(t.is_default for t in tracks):
        tracks[0].is_default = True
        tracks[0].selection_reason = (
            f"Primary current-line option per algorithm {algo['id']}: "
            "selected default was filtered; promoted first remaining current-line track"
        )

    fda = _build_fda_compliance(algo, tracks, entities, result.warnings)

    # KB state snapshot (per CHARTER §10.2 — immutable audit)
    kb_state = {
        "loaded_entities": len(entities),
        "indications_used": [t.indication_id for t in tracks],
        "sequencing_indications": [t.indication_id for t in sequencing_tracks],
        "algorithm_version": algo.get("last_reviewed"),
    }

    plan_id = f"PLAN-{(result.patient_id or 'ANONYMOUS').upper()}-V{plan_version}"
    result.plan = Plan(
        id=plan_id,
        patient_id=result.patient_id or "ANONYMOUS",
        version=plan_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        supersedes=supersedes,
        superseded_by=None,
        revision_trigger=revision_trigger,
        patient_snapshot=patient,
        algorithm_id=algo["id"],
        knowledge_base_state=kb_state,
        tracks=tracks,
        sequencing_tracks=sequencing_tracks,
        fda_compliance=fda,
        trace=trace,
        warnings=result.warnings,
        annotations=[],
    )

    # Back-compat fields for existing tests
    if tracks:
        result.default_indication_id = tracks[0].indication_id
        result.default_indication = tracks[0].indication_data
        if len(tracks) >= 2:
            result.alternative_indication_id = tracks[1].indication_id
            result.alternative_indication = tracks[1].indication_data

    # Resolve KB references that the render layer needs but that aren't
    # carried on the Plan structure: disease (for archetype + etiological_factors),
    # tests (for priority_class on pre-treatment investigations table),
    # red_flags (for PRO/CONTRA categorization with definitions).
    test_ids: set[str] = set()
    redflag_ids: set[str] = set()
    drug_ids: set[str] = set()
    for t in tracks:
        ind = t.indication_data or {}
        test_ids.update(ind.get("required_tests") or [])
        test_ids.update(ind.get("desired_tests") or [])
        redflag_ids.update(ind.get("red_flags_triggering_alternative") or [])
        # Drugs referenced by the regimen on this track — needed for
        # render-time NSZU badge lookup (engine/_nszu.py). Not consulted
        # by the engine itself (CHARTER §8.3 invariant).
        reg = t.regimen_data or {}
        for comp in reg.get("components") or []:
            did = comp.get("drug_id") if isinstance(comp, dict) else None
            if did:
                drug_ids.add(did)
    # Algorithm-referenced red flags too (decision tree)
    for step in algo.get("decision_tree") or []:
        ev = step.get("evaluate") or {}
        for clause in (ev.get("any_of") or []) + (ev.get("all_of") or []):
            rf = clause.get("red_flag") if isinstance(clause, dict) else None
            if rf:
                redflag_ids.add(rf)

    result.kb_resolved = {
        "disease": _resolve(entities, disease_id),
        "algorithm": algo,
        "tests": {tid: _resolve(entities, tid) for tid in test_ids if _resolve(entities, tid)},
        "red_flags": {rid: _resolve(entities, rid) for rid in redflag_ids if _resolve(entities, rid)},
        "drugs": {did: _resolve(entities, did) for did in drug_ids if _resolve(entities, did)},
    }

    # Experimental track (Phase C of UA-ingestion plan). Append-only,
    # never feeds back into selection — engine output above is final.
    # Triggered when either a live search_fn or a prewarmed cache_root
    # is provided. Cache-only mode (Pyodide) returns hits when present
    # and a "search not configured" empty bundle on miss.
    if experimental_search_fn is not None or experimental_cache_root is not None:
        disease_data = result.kb_resolved.get("disease") or {}
        disease_term = (
            ((disease_data.get("names") or {}).get("english"))
            or ((disease_data.get("names") or {}).get("preferred"))
            or disease_id
        )
        biomarker_term = _first_truthy_biomarker(patient.get("biomarkers") or {})
        try:
            result.experimental_options = enumerate_experimental_options(
                disease_id=disease_id,
                disease_term=disease_term,
                biomarker_profile=biomarker_term,
                line_of_therapy=line,
                search_fn=experimental_search_fn,
                cache_root=Path(experimental_cache_root) if experimental_cache_root else None,
            )
        except Exception as exc:
            result.warnings.append(f"experimental options skipped: {exc}")

    # Access Matrix (Phase D of UA-ingestion plan §3.1 + §4). Render-time
    # aggregation of UA-availability metadata across tracks + experimental
    # trials. NEVER read back by engine selection — the invariant test
    # asserts plan signature is unchanged when all drugs are monkeypatched
    # to registered=False.
    try:
        result.plan.access_matrix = build_access_matrix(
            tracks,
            entities,
            experimental_options=result.experimental_options,
        )
    except Exception as exc:
        result.warnings.append(f"access matrix skipped: {exc}")

    # Variant actionability (ESCAT / OncoKB) — match patient biomarkers
    # against BiomarkerActionability cells for this disease. Render-time
    # context only; engine never re-reads tier values to rank tracks
    # (CHARTER §8.3 — tracks come from the declarative Algorithm above).
    try:
        hits = find_matching_actionability(
            patient.get("biomarkers") or {},
            disease_id,
            entities,
        )
        result.plan.variant_actionability = [
            VariantActionabilityHit(**h) for h in hits
        ]
    except Exception as exc:
        result.warnings.append(f"variant actionability skipped: {exc}")

    # ── Actionability precision-medicine layer ──────────────────────────
    # Phase 3b wiring (safe-rollout v3 §3.2). Surface-only — added AFTER
    # tracks/actionability are final. CHARTER §8.3 invariant: nothing
    # below influences track selection (those are done above).
    # Default OFF: caller must pass actionability_enabled=True AND a client.
    # Coexists with master's plan.variant_actionability (static-KB lookup
    # via _actionability.find_matching_actionability) — this layer adds
    # dynamic CIViC snapshot lookup for biomarkers with actionability_lookup.
    if actionability_enabled and actionability_client is not None:
        try:
            from .actionability_extract import extract_actionability_queries
            from .actionability_conflict import annotate_layer_with_conflicts
            from .actionability_types import ActionabilityResult, ActionabilityError
            from .oncotree_fallback import resolve_oncotree_code

            disease_data = result.kb_resolved.get("disease") or {}
            oncotree, pan_tumor_fallback = resolve_oncotree_code(disease_data)

            hints: list[tuple[str, str, str]] = []
            for bio_id, _value in (patient.get("biomarkers") or {}).items():
                bio_record = _resolve(entities, bio_id) or {}
                hint = (
                    bio_record.get("actionability_lookup")
                    or bio_record.get("oncokb_lookup")
                )
                if isinstance(hint, dict) and hint.get("gene") and hint.get("variant"):
                    hints.append((bio_id, hint["gene"], hint["variant"]))

            queries = extract_actionability_queries(hints, oncotree_code=oncotree)
            if queries:
                results_list = actionability_client.batch_lookup(queries)
                ok_results = [r for r in results_list if isinstance(r, ActionabilityResult)]
                errors = [r for r in results_list if isinstance(r, ActionabilityError)]

                layer = ActionabilityLayer(
                    results=ok_results,
                    errors=errors,
                    pan_tumor_fallback_used=pan_tumor_fallback,
                )
                annotate_layer_with_conflicts(layer, tracks)
                result.actionability_layer = layer
        except Exception as exc:  # noqa: BLE001 — fail-open contract
            result.warnings.append(f"actionability layer skipped: {exc}")

    return result


def _first_truthy_biomarker(biomarkers: dict) -> Optional[str]:
    """Pick a representative biomarker term for the ctgov query.

    Patient biomarker dicts vary in shape — values may be bool, str,
    or nested dict. We prefer keys whose value is True or a positive
    string ("positive", "mutated", "amplified"). Returns the human
    label form (e.g. `BIO-EGFR-MUT` → `EGFR mutation`-ish), or None
    when no positive biomarker is present.

    Engine doesn't read this — it only feeds the trial query.
    """

    if not biomarkers:
        return None
    for key, val in biomarkers.items():
        if val is True:
            return _humanize_biomarker_key(key)
        if isinstance(val, str) and val.lower() in {
            "positive", "pos", "mutated", "mut", "amplified", "high"
        }:
            return _humanize_biomarker_key(key)
    return None


def _humanize_biomarker_key(key: str) -> str:
    """`BIO-EGFR-MUTATION` → `EGFR mutation`; falls back to the raw key."""
    raw = key
    if raw.upper().startswith("BIO-"):
        raw = raw[4:]
    return raw.replace("_", " ").replace("-", " ").lower()


__all__ = ["PlanResult", "generate_plan"]
