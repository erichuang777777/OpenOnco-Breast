"""End-to-end render-layer tests for the §20 PreventionPlan path
(RATIFIED 2026-05-18, KSS §20.4 step 5).

Companion to `tests/test_prevention_engine.py`, which validates the
engine side. These tests assert that `render_plan_html()` accepts the
PreventionPlan shape (Plan.algorithm_id is None, prevention-intent
Indications, RF-driven trace) and produces valid HTML without crashing
or leaking the literal string "None" into user-visible content.

Invariants checked (CHARTER §15):
  * C1 (HCP-only): PreventionPlan still targets HCP — patient-mode is
    a translation of the same Plan structure.
  * C4 (≥2 tracks): both prevention tracks render as track blocks.
  * C6 (no automation-bias UX): FDA `automation_bias_warning` text
    surfaces in the rendered HTML.

Render-layer crash regression guard: line 423 in `render.py` reads
`plan.algorithm_id or ""` and would otherwise interpolate `None` into
visible text; line 392 already falls back gracefully. The orchestrator
(`mdt_orchestrator.py:1481-ish`) also reads `plan.algorithm_id` for
provenance-event summaries — the fix substitutes a fallback label so
the rendered MDT events never read "алгоритму None.".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from knowledge_base.engine import generate_plan, render_plan_html

REPO_ROOT = Path(__file__).parent.parent
KB_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
EXAMPLES = REPO_ROOT / "examples"

# Fixture gate: the e2e tests below need the §20 prevention engine
# path AND the canonical prevention patient fixture. Either is absent
# on a checkout where the prevention branch has not landed yet — in
# that case skip the e2e block rather than fail with a misleading
# FileNotFoundError. The direct-orchestrator unit test below
# (`test_mdt_bootstrap_provenance_handles_none_algorithm_id`) has its
# own schema gate and runs even when the fixture is absent.
_PREVENTION_PATIENT_FIXTURE = EXAMPLES / "patient_chronic_hcv_prevention.json"
_skip_if_no_prevention_fixture = pytest.mark.skipif(
    not _PREVENTION_PATIENT_FIXTURE.is_file(),
    reason=(
        "examples/patient_chronic_hcv_prevention.json absent — "
        "§20 prevention engine path is not on this checkout."
    ),
)

_TAG_PATTERN = re.compile(r"<[^>]*>")


def _patient(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _visible_text(html: str) -> str:
    """Strip HTML tags + <style>/<script> blocks. Leaves the body text
    a clinician (or patient, in patient mode) actually reads."""
    no_style = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    no_script = re.sub(r"<script[^>]*>.*?</script>", "", no_style, flags=re.DOTALL)
    return _TAG_PATTERN.sub(" ", no_script)


# ── HCP-mode render (default) ─────────────────────────────────────────────


@_skip_if_no_prevention_fixture
def test_prevention_plan_renders_html_without_exception():
    """`render_plan_html` accepts a PreventionPlan (algorithm_id=None,
    intent=prevention tracks) and emits non-empty HTML."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    assert result.plan is not None, "PreventionPlan should be built first"
    assert result.plan.algorithm_id is None, (
        "Precondition: prevention path sets algorithm_id=None — if this "
        "fails the engine wiring regressed, not the renderer."
    )

    html = render_plan_html(result)
    assert isinstance(html, str)
    assert len(html) > 0, "render_plan_html returned empty string for PreventionPlan"
    # Document shell (treatment-mode path)
    assert "<html" in html.lower()


@_skip_if_no_prevention_fixture
def test_prevention_plan_renders_both_track_indications():
    """§15.2 C4 ≥2-tracks invariant: both prevention tracks must surface
    in the rendered HTML — DAA standard + observation alternative."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    html = render_plan_html(result)

    # The Indication ID is the most stable identifier the render layer
    # exposes in the tracks block (dt/dd pair).
    assert "IND-CHRONIC-HCV-PREVENTION-DAA" in html, (
        "Standard prevention track (DAA) indication id missing from HTML"
    )
    assert "IND-CHRONIC-HCV-PREVENTION-OBSERVATION" in html, (
        "Alternative prevention track (observation) indication id missing from HTML"
    )


@_skip_if_no_prevention_fixture
def test_prevention_plan_has_prevention_specific_fda_criterion_4_text():
    """§15 Criterion 4 invariant: rendered HTML carries the prevention-
    specific intended_use phrasing emitted by
    `_build_prevention_fda_compliance`. Treatment-path phrasing
    ("tumor-board discussion") must not be substituted by accident."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    html = render_plan_html(result)
    visible = _visible_text(html).lower()

    # Tokens unique to the prevention FDA synthesizer (vs treatment one).
    assert "asymptomatic" in visible, (
        "Prevention-specific FDA Criterion-4 'asymptomatic individuals' "
        "phrasing absent from rendered HTML — render may have dropped "
        "the prevention FDAComplianceMetadata block."
    )
    assert "at-risk" in visible, (
        "Prevention-specific FDA Criterion-4 'at-risk' phrasing absent "
        "from rendered HTML."
    )


@_skip_if_no_prevention_fixture
def test_prevention_plan_carries_automation_bias_warning():
    """§15 C6: automation-bias warning must surface in the rendered HTML
    for both treatment AND prevention plans (no UX shortcut allowed for
    the prevention persona)."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    html = render_plan_html(result)
    visible = _visible_text(html).lower()

    # The prevention synthesizer's wording: "Both prevention options
    # below are presented for review" — pick a stable substring.
    assert "presented for review" in visible, (
        "automation_bias_warning sentence missing from rendered "
        "PreventionPlan HTML — CHARTER §15 C6 violation."
    )


@_skip_if_no_prevention_fixture
def test_prevention_plan_no_visible_literal_none_in_html():
    """Render-layer crash/None-leak regression guard.

    `plan.algorithm_id is None` for PreventionPlan output (KSS §20.2).
    The renderer must NOT interpolate `None` into user-visible text.

    Tight match: scan for `>None<` (a literal "None" as a tag body),
    `>None ` / ` None<` (None bordered by tag boundary + whitespace),
    and `None.` as a sentence terminator (the mdt_orchestrator
    f-string bug). Loose `'None' in html` would false-positive on
    substrings like "Anonymous" (the synthetic patient_id) or CSS
    classes like "track--none"."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    html = render_plan_html(result)

    # Tag-bounded literal "None" — the most common interpolation leak shape.
    assert ">None<" not in html, (
        "Literal 'None' interpolated as a tag body — likely from a "
        "missing or-fallback on an Optional field (algorithm_id, "
        "regimen_id, etc.)."
    )
    # Pre-fix mdt_orchestrator pattern: "алгоритму None." would surface
    # in any rendered provenance summary. Guard for both the UA form and
    # any English equivalent.
    assert " None." not in _visible_text(html), (
        "Sentence-terminator 'None.' in visible text — likely the "
        "mdt_orchestrator f-string regression."
    )
    assert "алгоритму None" not in html, (
        "Mdt_orchestrator pre-fix 'алгоритму None' regression — "
        "Optional[str] algorithm_id must use a graceful fallback label."
    )


@_skip_if_no_prevention_fixture
def test_prevention_plan_render_does_not_regress_disease_label():
    """`_diagnosis_name` falls back to `plan_result.disease_id or ""` —
    for prevention, both are absent (disease_id is None because no
    confirmed Disease was matched). The header should still render;
    the disease label may be empty but must not contain 'None'."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    assert result.disease_id is None, (
        "Precondition: prevention path leaves PlanResult.disease_id=None"
    )
    html = render_plan_html(result)

    # Document title block ("План лікування — …") should still render.
    assert "doc-header" in html or "doc-title" in html, (
        "Document header missing from rendered HTML"
    )
    # The header substring "План лікування — None" would be the literal
    # bug shape; guard for it explicitly.
    assert "— None" not in html, (
        "Disease title interpolated literal 'None' — _diagnosis_name "
        "fallback regressed."
    )


# ── Direct orchestrator-fix regression guard ──────────────────────────────


def test_mdt_bootstrap_provenance_handles_none_algorithm_id():
    """Direct exercise of the `mdt_orchestrator._bootstrap_provenance`
    f-string fix.

    Why a direct unit test in addition to the e2e render tests above:
    the bug only manifests for trace entries that carry a non-empty
    `fired_red_flags` array (the inner loop guard at line 1469 — what
    was line 1481 pre-fix). The prevention engine's current trace
    entries use `{"step": "prevention_rf_fired", "rf_id": ...}` shape
    — they have NO `fired_red_flags` list, so the buggy inner-loop
    body wouldn't fire even when the orchestrator runs on a real
    PreventionPlan. This test synthesizes a worst-case trace entry
    so the regression guard actually exercises the bug path.

    Construction: build a minimal PreventionPlan-shape Plan with
    `algorithm_id=None` and a trace entry containing
    `fired_red_flags=["RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY"]`.
    Run `_bootstrap_provenance` directly; assert no event summary
    contains the literal substring "алгоритму None." or " None.".
    """
    from datetime import datetime, timezone

    import pytest as _pytest

    from knowledge_base.engine.mdt_orchestrator import _bootstrap_provenance
    from knowledge_base.engine.plan import PlanResult
    from knowledge_base.schemas import (
        FDAComplianceMetadata,
        Plan,
        PlanTrack,
    )

    # Schema gate: Plan.algorithm_id must be Optional[str] (KSS §20.2
    # ratification 2026-05-18) for this regression guard to be
    # meaningful. If we're running on a checkout where the schema
    # hasn't been amended yet, skip — the bug under test cannot occur
    # because Pydantic would reject the input before
    # _bootstrap_provenance is ever called.
    try:
        Plan.model_validate(
            {
                "id": "PLAN-SCHEMA-PROBE",
                "patient_id": "X",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "patient_snapshot": {},
                "algorithm_id": None,
                "tracks": [
                    {
                        "track_id": "t",
                        "label": "t",
                        "indication_id": "IND-X",
                    }
                ],
                "fda_compliance": {
                    "intended_use": "x",
                    "hcp_user_specification": "x",
                    "patient_population_match": "x",
                    "algorithm_summary": "x",
                },
            }
        )
    except Exception:
        _pytest.skip(
            "Plan.algorithm_id is not yet Optional on this checkout — "
            "schema amendment per KSS §20.2 must land first."
        )

    plan = Plan(
        id="PLAN-TEST-MDT-NONE-ALGO-V1",
        patient_id="TEST-MDT-NONE-ALGO",
        version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        patient_snapshot={"patient_id": "TEST-MDT-NONE-ALGO"},
        algorithm_id=None,  # PreventionPlan invariant per KSS §20.2
        knowledge_base_state={
            "fired_prevention_redflags": [
                "RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY"
            ],
            "prevention_targets": ["DIS-HCV-MZL"],
            "algorithm_version": None,
        },
        tracks=[
            PlanTrack(
                track_id="standard",
                label="Стандартний план",
                indication_id="IND-CHRONIC-HCV-PREVENTION-DAA",
                is_default=True,
                selection_reason="test",
            ),
            PlanTrack(
                track_id="surveillance",
                label="Активне спостереження",
                indication_id="IND-CHRONIC-HCV-PREVENTION-OBSERVATION",
                is_default=False,
                selection_reason="test",
            ),
        ],
        fda_compliance=FDAComplianceMetadata(
            intended_use="prevention test",
            hcp_user_specification="HCP test",
            patient_population_match="at-risk asymptomatic adults",
            algorithm_summary="prevention test",
        ),
        # Worst-case trace shape: fired_red_flags non-empty so the
        # inner loop body — the actual bug site — runs.
        trace=[
            {
                "step": "synthetic_for_test",
                "fired_red_flags": [
                    "RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY"
                ],
                "winner_red_flag": (
                    "RF-CHRONIC-HCV-NHL-PREVENTION-OPPORTUNITY"
                ),
            }
        ],
    )
    plan_result = PlanResult(
        patient_id="TEST-MDT-NONE-ALGO",
        disease_id=None,
        algorithm_id=None,
        plan=plan,
    )

    graph = _bootstrap_provenance(plan_result, [], [], [], [])
    events = list(graph.events)
    assert events, "provenance graph should contain >=1 event"

    flagged_risk_events = [
        e for e in events if getattr(e, "event_type", "") == "flagged_risk"
    ]
    assert flagged_risk_events, (
        "fired_red_flags entry should produce at least one flagged_risk event"
    )
    for ev in flagged_risk_events:
        summary = getattr(ev, "summary", "")
        assert "алгоритму None" not in summary, (
            f"f-string regression: event summary contains 'алгоритму "
            f"None': {summary!r}"
        )
        assert " None." not in summary, (
            f"f-string regression: event summary contains literal "
            f"'None.': {summary!r}"
        )
        # Positive assertion — the fallback label is present.
        assert "профілактичного маршруту" in summary, (
            f"Expected prevention-path fallback label in summary: {summary!r}"
        )


# ── Patient-mode render (PATIENT_MODE_SPEC §3) ─────────────────────────────


@_skip_if_no_prevention_fixture
def test_prevention_plan_patient_mode_renders_without_exception():
    """`render_plan_html(mode='patient')` accepts a PreventionPlan and
    emits a valid patient-bundle wrapper. PATIENT_MODE_SPEC §3: patient
    bundle is a translation of the HCP-targeted Plan; the same Plan
    structure must round-trip through the patient renderer for the
    prevention persona too."""
    result = generate_plan(
        _patient("patient_chronic_hcv_prevention.json"), kb_root=KB_ROOT
    )
    html = render_plan_html(result, mode="patient")
    assert '<div class="patient-report">' in html, (
        "Patient-mode HTML must wrap content in <div class='patient-report'>"
    )
    # Same None-leak guard for the patient bundle path.
    assert ">None<" not in html
    assert " None." not in _visible_text(html)
