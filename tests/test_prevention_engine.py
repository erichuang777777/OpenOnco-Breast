"""End-to-end tests for the §20 PreventionPlan path (RATIFIED 2026-05-18).

Validates that a patient with no confirmed Disease but with ≥1 fired
prevention-eligible RedFlag routes to a PreventionPlan with ≥2 prevention-
intent Indication tracks (CHARTER §15.2 C4 invariant preserved).

v0.2-A anchor: chronic HCV → DAA prevention pathway. Tests both:
  - positive prevention case (chronic HCV → 2 prevention tracks)
  - negative case (empty patient → no plan, existing warning path)
  - treatment-path regression (HCV-MZL patient with confirmed disease
    still routes to ALGO-HCV-MZL-1L, prevention path doesn't intercept)
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_base.engine import generate_plan

REPO_ROOT = Path(__file__).parent.parent
KB_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
EXAMPLES = REPO_ROOT / "examples"


def _patient(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


# ── Prevention positive: chronic HCV routes to PreventionPlan ─────────────


def test_chronic_hcv_routes_to_prevention_plan():
    """Patient with HCV-RNA detectable + no Disease → PreventionPlan."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    assert result.plan is not None, "PreventionPlan should be built"
    # KSS §20.2: prevention path has no algorithm
    assert result.algorithm_id is None
    assert result.plan.algorithm_id is None
    assert result.disease_id is None


def test_chronic_hcv_prevention_has_two_tracks():
    """§15.2 C4: ≥2 tracks invariant on PreventionPlan."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    assert len(result.plan.tracks) == 2
    track_ids = {t.indication_id for t in result.plan.tracks}
    assert "IND-CHRONIC-HCV-PREVENTION-DAA" in track_ids
    assert "IND-CHRONIC-HCV-PREVENTION-OBSERVATION" in track_ids


def test_chronic_hcv_prevention_daa_is_default():
    """DAA pathway is the default (recommended) prevention track."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    default = next(t for t in result.plan.tracks if t.is_default)
    assert default.indication_id == "IND-CHRONIC-HCV-PREVENTION-DAA"
    assert default.regimen_data is not None
    assert default.regimen_data["id"] == "REG-DAA-SOF-VEL"


def test_chronic_hcv_prevention_rf_recorded_in_kb_state():
    """kb_state surfaces the fired prevention RF for audit/render."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    fired = result.plan.knowledge_base_state.get("fired_prevention_redflags") or []
    assert "RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY" in fired


def test_chronic_hcv_prevention_target_recorded():
    """kb_state surfaces the cancer-being-prevented for the header."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    targets = result.plan.knowledge_base_state.get("prevention_targets") or []
    assert "DIS-HCV-MZL" in targets


def test_chronic_hcv_prevention_fda_compliance_is_prevention_specific():
    """§15 Criterion-4 metadata uses prevention phrasing, not treatment."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    fda = result.plan.fda_compliance
    assert "prevention" in fda.intended_use.lower()
    assert "asymptomatic" in fda.intended_use.lower()
    # HCP-only invariant per §15 C1
    assert (
        "genetic counselor" in fda.hcp_user_specification.lower()
        or "primary-care" in fda.hcp_user_specification.lower()
    )


def test_chronic_hcv_prevention_trace_records_rf_firing():
    """trace[] captures which prevention RF fired and why."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    assert result.plan.trace
    first = result.plan.trace[0]
    assert first.get("step") == "prevention_rf_fired"
    assert first.get("rf_id") == "RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY"
    assert first.get("risk_category") == "infectious"


# ── Prevention negative: no RF fires → no plan ────────────────────────────


def test_no_prevention_rf_falls_through_to_warning():
    """Patient with no Disease AND no fired prevention RF → no plan,
    existing 'Could not resolve disease' warning preserved."""
    empty_patient = {
        "patient_id": "PREV-NEG-001",
        "biomarkers": {},
        "demographics": {"age": 50, "ecog": 0},
    }
    result = generate_plan(empty_patient, kb_root=KB_ROOT)
    assert result.plan is None
    assert any(
        "Could not resolve disease" in w for w in result.warnings
    ), result.warnings


# ── Regression: treatment path still works for confirmed disease ──────────


def test_hcv_mzl_treatment_path_unaffected_by_prevention_branch():
    """Patient with confirmed HCV-MZL disease still routes to the
    treatment algorithm. Prevention path must not intercept."""
    treatment_patient = {
        "patient_id": "TREAT-REG-001",
        "disease": {"id": "DIS-HCV-MZL"},
        "biomarkers": {"BIO-HCV-RNA": "detectable", "BIO-CD20-IHC": "positive"},
        "line_of_therapy": 1,
        "demographics": {"age": 60, "ecog": 1, "decompensated_cirrhosis": False},
        "findings": {"anti_hcv": "positive", "hcv_rna_positive": True},
    }
    result = generate_plan(treatment_patient, kb_root=KB_ROOT)
    assert result.disease_id == "DIS-HCV-MZL"
    assert result.algorithm_id == "ALGO-HCV-MZL-1L"
    assert result.plan is not None
    assert result.plan.algorithm_id == "ALGO-HCV-MZL-1L"  # treatment, not prevention


# ── Schema-level sanity: new fields surface on loaded entities ────────────


def test_prevention_indication_intent_loads_as_enum():
    """IND-CHRONIC-HCV-PREVENTION-DAA loads with intent=prevention via
    the new field, not as default treatment."""
    from knowledge_base.validation.loader import load_content

    load = load_content(KB_ROOT)
    ind = load.entities_by_id["IND-CHRONIC-HCV-PREVENTION-DAA"]["data"]
    assert ind.get("intent") == "prevention"


def test_prevention_redflag_risk_category_loads():
    """RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY loads with
    risk_category=infectious via the new field."""
    from knowledge_base.validation.loader import load_content

    load = load_content(KB_ROOT)
    rf = load.entities_by_id["RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY"]["data"]
    assert rf.get("risk_category") == "infectious"


def test_biomarker_applicable_in_asymptomatic_loads():
    """BIO-HCV-RNA loads with applicable_in_asymptomatic=true after
    v0.2-A foundation edit."""
    from knowledge_base.validation.loader import load_content

    load = load_content(KB_ROOT)
    bio = load.entities_by_id["BIO-HCV-RNA"]["data"]
    assert bio.get("applicable_in_asymptomatic") is True
    contexts = bio.get("clinical_context") or []
    assert "screening_surveillance" in contexts
