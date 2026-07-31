"""Trial outlook scoring — unit tests.

Module: knowledge_base/engine/trial_outlook.py
Schema: knowledge_base/schemas/experimental_option.py (TrialOutlook)

Five behaviour groups:
  1. Biomarker stratification — enriched / open_label / unclear cases.
  2. Design flags — phase1_only, small_enrollment, surrogate_endpoint_only,
     single_country.
  3. Combined scoring via `score_trial`.
  4. Cache back-compat: an ExperimentalTrial JSON without `outlook`
     round-trips through model_validate (older cache files).
  5. Integration with `_to_trial`: stratification flows from the
     enumerator's `biomarker_profile` parameter into each trial.

Architectural invariant (CHARTER §8.3): the engine never reads `outlook`
back as a selection signal. That invariant is guarded by the existing
`tests/test_experimental_options.py::test_generate_plan_attaches_*`
tests; this file just validates the scorer's contract.
"""

from __future__ import annotations

from knowledge_base.engine.trial_outlook import detect_age_sex_screen, score_trial
from knowledge_base.schemas.experimental_option import (
    ExperimentalTrial,
    TrialOutlook,
)


def _study(
    *,
    nct_id: str = "NCT-T",
    phase: str = "PHASE3",
    enrollment: int = 600,
    primary_outcomes: list[str] | None = None,
    countries: list[str] | None = None,
    eligibility: str = "",
) -> dict:
    """Mimics one parsed-ctgov study dict."""
    return {
        "nct_id": nct_id,
        "title": "Trial",
        "status": "RECRUITING",
        "phase": phase,
        "enrollment": enrollment,
        "primary_outcomes": primary_outcomes
        if primary_outcomes is not None
        else ["Overall survival"],
        "countries": countries or ["US", "DE"],
        "eligibility_criteria": eligibility,
    }


# ── 1. Biomarker stratification ─────────────────────────────────────────


def test_stratification_enriched_when_inclusion_mentions_biomarker():
    out = score_trial(
        _study(),
        biomarker_term="EGFR mutation",
        inclusion_summary="Inclusion: documented EGFR exon 19 deletion or L858R.",
        exclusion_summary="Exclusion: prior chemotherapy.",
    )
    assert out.biomarker_stratification == "enriched"
    assert any("inclusion criteria reference" in n.lower() for n in out.notes)


def test_stratification_open_label_when_no_biomarker_term():
    out = score_trial(
        _study(),
        biomarker_term=None,
        inclusion_summary="Inclusion: ECOG 0-1.",
        exclusion_summary="Exclusion: brain metastases.",
    )
    assert out.biomarker_stratification == "open_label"


def test_stratification_open_label_when_biomarker_absent_from_eligibility():
    out = score_trial(
        _study(),
        biomarker_term="ALK fusion",
        inclusion_summary="Inclusion: ECOG 0-1, age >= 18.",
        exclusion_summary="Exclusion: active CNS disease.",
    )
    assert out.biomarker_stratification == "open_label"


def test_stratification_unclear_when_biomarker_only_in_exclusion():
    out = score_trial(
        _study(),
        biomarker_term="HER2 amplification",
        inclusion_summary="Inclusion: ECOG 0-1.",
        exclusion_summary="Exclusion: known HER2-positive disease.",
    )
    assert out.biomarker_stratification == "unclear"
    assert any("exclusion" in n.lower() for n in out.notes)


def test_stratification_strips_descriptor_words():
    """'EGFR mutation' should match 'EGFR-mutant' inclusion text — the
    stopword stripper turns the term into the bare gene token."""
    out = score_trial(
        _study(),
        biomarker_term="EGFR mutation",
        inclusion_summary="Inclusion: EGFR-mutant non-small cell lung cancer.",
        exclusion_summary="",
    )
    assert out.biomarker_stratification == "enriched"


def test_stratification_unclear_on_partial_token_match():
    """A multi-token biomarker like 'BRAF V600E' where only one token
    appears in inclusion is unclear, not enriched."""
    out = score_trial(
        _study(),
        biomarker_term="BRAF V600E",
        inclusion_summary="Inclusion: BRAF mutation (any).",
        exclusion_summary="",
    )
    assert out.biomarker_stratification == "unclear"


# ── 2. Design flags ─────────────────────────────────────────────────────


def test_phase1_only_flagged():
    out = score_trial(_study(phase="PHASE1"), biomarker_term=None)
    assert "phase1_only" in out.design_flags


def test_phase1_phase2_combo_not_flagged_as_phase1_only():
    out = score_trial(_study(phase="PHASE1 / PHASE2"), biomarker_term=None)
    assert "phase1_only" not in out.design_flags


def test_small_enrollment_flagged():
    out = score_trial(_study(enrollment=24), biomarker_term=None)
    assert "small_enrollment" in out.design_flags
    assert any("N=24" in n for n in out.notes)


def test_zero_enrollment_not_flagged_as_small():
    """Missing/zero enrollment is unknown, not 'small N'."""
    out = score_trial(_study(enrollment=0), biomarker_term=None)
    assert "small_enrollment" not in out.design_flags


def test_large_enrollment_not_flagged():
    out = score_trial(_study(enrollment=600), biomarker_term=None)
    assert "small_enrollment" not in out.design_flags


def test_surrogate_endpoint_flagged_when_no_os():
    out = score_trial(
        _study(primary_outcomes=["Progression-free survival", "Objective response rate"]),
        biomarker_term=None,
    )
    assert "surrogate_endpoint_only" in out.design_flags


def test_surrogate_not_flagged_when_os_present():
    out = score_trial(
        _study(primary_outcomes=["Progression-free survival", "Overall survival"]),
        biomarker_term=None,
    )
    assert "surrogate_endpoint_only" not in out.design_flags


def test_single_country_flagged():
    out = score_trial(_study(countries=["US"]), biomarker_term=None)
    assert "single_country" in out.design_flags


def test_two_countries_not_flagged():
    out = score_trial(_study(countries=["US", "DE"]), biomarker_term=None)
    assert "single_country" not in out.design_flags


# ── 2b. Age / sex screen ─────────────────────────────────────────────────


def test_age_sex_screen_unknown_when_no_patient_data():
    screen, note = detect_age_sex_screen("18 Years", "N/A", "ALL", None, None)
    assert screen == "unknown"
    assert note is None


def test_age_sex_screen_unknown_when_trial_has_no_constraint():
    screen, note = detect_age_sex_screen(None, None, "ALL", 58, "female")
    assert screen == "unknown"
    assert note is None


def test_age_sex_screen_mismatch_below_minimum_age():
    screen, note = detect_age_sex_screen("18 Years", "N/A", "ALL", 12, None)
    assert screen == "mismatch"
    assert "below the trial minimum" in note


def test_age_sex_screen_mismatch_above_maximum_age():
    screen, note = detect_age_sex_screen(None, "65 Years", "ALL", 80, None)
    assert screen == "mismatch"
    assert "above the trial maximum" in note


def test_age_sex_screen_match_within_age_range():
    screen, note = detect_age_sex_screen("18 Years", "75 Years", "ALL", 58, None)
    assert screen == "match"
    assert "within the trial's stated range" in note


def test_age_sex_screen_mismatch_on_sex_restriction():
    screen, note = detect_age_sex_screen(None, None, "MALE", None, "female")
    assert screen == "mismatch"
    assert "restricted to MALE" in note


def test_age_sex_screen_match_on_sex_restriction():
    screen, note = detect_age_sex_screen(None, None, "FEMALE", None, "female")
    assert screen == "match"


def test_age_sex_screen_sex_all_is_not_a_restriction():
    screen, note = detect_age_sex_screen(None, None, "ALL", None, "male")
    assert screen == "unknown"
    assert note is None


def test_age_sex_screen_parses_months():
    # A trial open from 6 months of age — a 58-year-old adult clears it.
    screen, _ = detect_age_sex_screen("6 Months", "N/A", "ALL", 58, None)
    assert screen == "match"


def test_age_sex_screen_age_mismatch_takes_priority_when_sex_matches():
    screen, note = detect_age_sex_screen("18 Years", "N/A", "FEMALE", 12, "female")
    assert screen == "mismatch"
    assert "below the trial minimum" in note


# ── 3. Combined — last_scored, notes alignment ──────────────────────────


def test_score_trial_sets_last_scored_to_today_by_default():
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = score_trial(_study(), biomarker_term=None)
    assert out.last_scored == today


def test_score_trial_respects_explicit_last_scored():
    out = score_trial(_study(), biomarker_term=None, last_scored="2026-01-01")
    assert out.last_scored == "2026-01-01"


def test_clean_phase3_global_trial_has_no_flags():
    """A textbook well-designed P3 (large N, OS endpoint, multi-country)
    surfaces zero design flags. With no biomarker context, stratification
    is open_label."""
    out = score_trial(
        _study(
            phase="PHASE3",
            enrollment=800,
            primary_outcomes=["Overall survival"],
            countries=["US", "DE", "UA", "JP"],
        ),
        biomarker_term=None,
    )
    assert out.design_flags == []
    assert out.biomarker_stratification == "open_label"
    assert out.notes == []


def test_score_trial_falls_back_to_raw_eligibility_when_no_split_provided():
    """When the caller passes no inclusion/exclusion splits (raw study
    use case), the function reads `eligibility_criteria` for matching."""
    out = score_trial(
        _study(eligibility="EGFR-mutant NSCLC, ECOG 0-1."),
        biomarker_term="EGFR mutation",
    )
    assert out.biomarker_stratification == "enriched"


# ── 4. Cache back-compat ────────────────────────────────────────────────


def test_experimental_trial_loads_without_outlook_field():
    """A JSON dict written before the `outlook` field existed must still
    validate — the field is Optional and defaults to None. This guards
    the on-disk ctgov_*.json cache files."""
    legacy_payload = {
        "nct_id": "NCT00000099",
        "title": "Pre-outlook cached trial",
        "status": "RECRUITING",
        "phase": "PHASE2",
    }
    trial = ExperimentalTrial.model_validate(legacy_payload)
    assert trial.outlook is None
    assert trial.nct_id == "NCT00000099"


def test_trial_outlook_round_trips_through_model_dump():
    out = score_trial(
        _study(phase="PHASE1", enrollment=20, countries=["US"]),
        biomarker_term="EGFR mutation",
        inclusion_summary="EGFR-mutant disease.",
        exclusion_summary="",
    )
    dumped = out.model_dump()
    restored = TrialOutlook.model_validate(dumped)
    assert restored.biomarker_stratification == out.biomarker_stratification
    assert restored.design_flags == out.design_flags
    assert restored.notes == out.notes


# ── 5. Integration with _to_trial ───────────────────────────────────────


def test_enumerate_attaches_outlook_to_each_trial():
    """The enumerator passes its `biomarker_profile` into score_trial via
    `_to_trial`, so each ExperimentalTrial.outlook is populated."""
    from knowledge_base.engine import (
        clear_experimental_cache,
        enumerate_experimental_options,
    )

    clear_experimental_cache()

    studies = [
        {
            "nct_id": "NCT-FLAURA2",
            "title": "FLAURA2",
            "status": "RECRUITING",
            "phase": "PHASE3",
            "enrollment": 586,
            "primary_outcomes": ["Progression-free survival"],
            "countries": ["US", "UA", "DE"],
            "eligibility_criteria": (
                "Inclusion Criteria:\n- EGFR-mutant NSCLC\n- ECOG 0-1\n\n"
                "Exclusion Criteria:\n- Active CNS disease"
            ),
        },
    ]

    opt = enumerate_experimental_options(
        disease_id="DIS-NSCLC",
        disease_term="NSCLC",
        biomarker_profile="EGFR mutation",
        line_of_therapy=1,
        search_fn=lambda **_: studies,
        cache=False,
    )

    assert len(opt.trials) == 1
    t = opt.trials[0]
    assert t.outlook is not None
    assert t.outlook.biomarker_stratification == "enriched"
    # FLAURA2 reports PFS without OS as primary -> surrogate flag
    assert "surrogate_endpoint_only" in t.outlook.design_flags
    # 3 countries -> no single-country flag, large N -> no small flag
    assert "single_country" not in t.outlook.design_flags
    assert "small_enrollment" not in t.outlook.design_flags


def test_render_surfaces_outlook_badges():
    """End-to-end: `render_plan_html` includes the outlook column header
    + badge content for at least one stratification + one design flag."""
    import json
    from pathlib import Path

    from knowledge_base.engine import (
        clear_experimental_cache,
        generate_plan,
        render_plan_html,
    )

    clear_experimental_cache()
    REPO_ROOT = Path(__file__).parent.parent
    KB_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
    EXAMPLES = REPO_ROOT / "examples"
    patient = json.loads(
        (EXAMPLES / "patient_mm_high_risk.json").read_text(encoding="utf-8")
    )

    def _stub(**_):
        return [
            {
                "nct_id": "NCT-OUTLOOK-1",
                "title": "Outlook signal carrier",
                "status": "RECRUITING",
                "phase": "PHASE1",
                "enrollment": 24,
                "primary_outcomes": ["Objective response rate"],
                "countries": ["US"],
                "eligibility_criteria": (
                    "Inclusion Criteria:\n- ECOG 0-1\n\n"
                    "Exclusion Criteria:\n- Active CNS disease"
                ),
            }
        ]

    res = generate_plan(patient, kb_root=KB_ROOT, experimental_search_fn=_stub)
    html = render_plan_html(res)

    assert 'class="trial-outlook"' in html
    assert "badge--design-flag" in html
    # Each design flag becomes one badge → at least one of the labels present
    assert ("Phase 1 only" in html or "Лише фаза 1" in html)
