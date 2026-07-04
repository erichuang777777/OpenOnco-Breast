"""Governance transparency badge — unit tests.

Module: knowledge_base/engine/render.py
Context: docs/reviews/fable-opinion.md Section 6. Discloses on the
rendered Plan when the underlying Algorithm's decision tree contains
unevaluated prose `condition:` clauses (see
docs/reviews/openonco-state-audit-2026-05-17.md) — purely a render-time
transparency signal. It must never affect engine selection (CHARTER
§8.3), never withhold a Plan, and never claim prose conditions are
harmless (they usually aren't — see
docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md for a case
where one very much mattered).
"""

from __future__ import annotations

from knowledge_base.engine.plan import PlanResult
from knowledge_base.engine.render import (
    _algorithm_has_unresolved_prose,
    _render_patient_strip,
)


def _plan_result(algorithm: dict) -> PlanResult:
    return PlanResult(
        patient_id="TEST-001",
        disease_id="DIS-TEST",
        algorithm_id=algorithm.get("id", "ALGO-TEST"),
        kb_resolved={"algorithm": algorithm},
    )


def test_no_prose_condition_returns_false():
    algo = {
        "id": "ALGO-CLEAN",
        "decision_tree": [
            {
                "step": 1,
                "evaluate": {"any_of": [{"finding": "ecog", "threshold": 1, "comparator": "<="}]},
            }
        ],
    }
    assert _algorithm_has_unresolved_prose(_plan_result(algo)) is False


def test_prose_condition_at_top_level_returns_true():
    algo = {
        "id": "ALGO-PROSE",
        "decision_tree": [
            {"step": 1, "evaluate": {"any_of": [{"condition": "HCV RNA positive AND indolent presentation"}]}}
        ],
    }
    assert _algorithm_has_unresolved_prose(_plan_result(algo)) is True


def test_prose_condition_nested_in_all_of_returns_true():
    algo = {
        "id": "ALGO-NESTED",
        "decision_tree": [
            {
                "step": 1,
                "evaluate": {
                    "all_of": [
                        {"finding": "histology", "value": "squamous"},
                        {"any_of": [{"condition": "significant comorbidity burden"}]},
                    ]
                },
            }
        ],
    }
    assert _algorithm_has_unresolved_prose(_plan_result(algo)) is True


def test_flat_finding_key_condition_is_not_prose():
    """A condition: clause that's a legitimate flat key (all-caps,
    underscored) must not trigger the badge."""
    algo = {
        "id": "ALGO-FLATKEY",
        "decision_tree": [
            {"step": 1, "evaluate": {"any_of": [{"condition": "BIO-EGFR-MUT"}]}}
        ],
    }
    assert _algorithm_has_unresolved_prose(_plan_result(algo)) is False


def test_no_decision_tree_returns_false():
    assert _algorithm_has_unresolved_prose(_plan_result({"id": "ALGO-EMPTY"})) is False


def test_missing_algorithm_in_kb_resolved_returns_false():
    result = PlanResult(patient_id="X", disease_id="DIS-X", algorithm_id="ALGO-X", kb_resolved={})
    assert _algorithm_has_unresolved_prose(result) is False


# ── Render integration ────────────────────────────────────────────────────


def test_patient_strip_includes_badge_when_prose_present():
    algo = {
        "id": "ALGO-PROSE",
        "decision_tree": [
            {"step": 1, "evaluate": {"any_of": [{"condition": "some unresolved prose"}]}}
        ],
    }
    html = _render_patient_strip(_plan_result(algo), target_lang="en")
    assert "badge--pending-review" in html
    assert "pending clinical review" in html


def test_patient_strip_omits_badge_when_no_prose():
    algo = {
        "id": "ALGO-CLEAN",
        "decision_tree": [
            {"step": 1, "evaluate": {"any_of": [{"finding": "ecog", "value": True}]}}
        ],
    }
    html = _render_patient_strip(_plan_result(algo), target_lang="en")
    assert "badge--pending-review" not in html


def test_patient_strip_badge_localized_uk():
    algo = {
        "id": "ALGO-PROSE",
        "decision_tree": [
            {"step": 1, "evaluate": {"any_of": [{"condition": "some unresolved prose"}]}}
        ],
    }
    html = _render_patient_strip(_plan_result(algo), target_lang="uk")
    assert "badge--pending-review" in html
    assert "клінічного перегляду" in html
