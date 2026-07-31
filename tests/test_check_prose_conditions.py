"""Prose-condition CI ratchet — unit tests.

Module: scripts/check_prose_conditions.py
Context: docs/reviews/openonco-state-audit-2026-05-17.md found 85% of
`condition:` clauses in Algorithm decision trees are unresolvable English
prose (silently evaluate False — see redflag_eval.py). A rescan on
2026-07-04 found the count had grown to 97%. This script doesn't fix the
existing backlog (that's a CHARTER §6.1 clinical-content change) — it
only stops new algorithm authoring from reproducing the pattern.
"""

from __future__ import annotations

import textwrap

import pytest

from scripts.check_prose_conditions import (
    check_against_baseline,
    count_conditions,
)


def _write_algo(tmp_path, name: str, yaml_text: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(yaml_text), encoding="utf-8")
    return path


# ── count_conditions ─────────────────────────────────────────────────────


def test_flat_finding_key_not_counted_as_prose(tmp_path):
    _write_algo(tmp_path, "algo_a.yaml", """
        id: ALGO-A
        decision_tree:
          - step: 1
            evaluate:
              any_of:
                - condition: "BIO-EGFR-MUT"
            if_true: {result: "IND-X"}
            if_false: {next_step: 2}
    """)
    counts = count_conditions(tmp_path)
    assert counts["algo_a.yaml"] == {"total": 1, "prose": 0}


def test_prose_condition_counted(tmp_path):
    _write_algo(tmp_path, "algo_b.yaml", """
        id: ALGO-B
        decision_tree:
          - step: 1
            evaluate:
              any_of:
                - condition: "HCV RNA positive AND indolent presentation"
            if_true: {result: "IND-Y"}
            if_false: {next_step: 2}
    """)
    counts = count_conditions(tmp_path)
    assert counts["algo_b.yaml"] == {"total": 1, "prose": 1}


def test_nested_all_of_any_of_walked(tmp_path):
    _write_algo(tmp_path, "algo_c.yaml", """
        id: ALGO-C
        decision_tree:
          - step: 1
            evaluate:
              all_of:
                - any_of:
                    - condition: "ECOG PS 0-2"
                    - finding: "ecog_ps"
                - condition: "BIO-KIT-MUT"
            if_true: {result: "IND-Z"}
            if_false: {next_step: 2}
    """)
    counts = count_conditions(tmp_path)
    # 2 condition: clauses total (ECOG prose + BIO-KIT-MUT flat); the
    # `finding:` sibling has no `condition:` key so isn't counted.
    assert counts["algo_c.yaml"] == {"total": 2, "prose": 1}


def test_red_flag_clause_without_condition_not_counted(tmp_path):
    _write_algo(tmp_path, "algo_d.yaml", """
        id: ALGO-D
        decision_tree:
          - step: 1
            evaluate:
              any_of:
                - red_flag: "RF-SOMETHING"
            if_true: {result: "IND-W"}
            if_false: {next_step: 2}
    """)
    counts = count_conditions(tmp_path)
    assert counts["algo_d.yaml"] == {"total": 0, "prose": 0}


def test_file_with_no_decision_tree_counts_zero(tmp_path):
    _write_algo(tmp_path, "algo_e.yaml", """
        id: ALGO-E
        decision_tree: []
    """)
    counts = count_conditions(tmp_path)
    assert counts["algo_e.yaml"] == {"total": 0, "prose": 0}


# ── check_against_baseline ───────────────────────────────────────────────


def test_new_file_with_prose_is_a_regression():
    current = {"algo_new.yaml": {"total": 1, "prose": 1}}
    baseline = {}
    problems = check_against_baseline(current, baseline)
    assert len(problems) == 1
    assert "algo_new.yaml" in problems[0]
    assert "new algorithm file" in problems[0]


def test_new_file_without_prose_is_not_a_regression():
    current = {"algo_new.yaml": {"total": 1, "prose": 0}}
    baseline = {}
    problems = check_against_baseline(current, baseline)
    assert problems == []


def test_existing_file_prose_increase_is_a_regression():
    current = {"algo_old.yaml": {"total": 5, "prose": 3}}
    baseline = {"algo_old.yaml": {"total": 5, "prose": 2}}
    problems = check_against_baseline(current, baseline)
    assert len(problems) == 1
    assert "increased from 2 to 3" in problems[0]


def test_existing_file_prose_decrease_is_not_a_regression():
    current = {"algo_old.yaml": {"total": 5, "prose": 1}}
    baseline = {"algo_old.yaml": {"total": 5, "prose": 2}}
    problems = check_against_baseline(current, baseline)
    assert problems == []


def test_existing_file_unchanged_is_not_a_regression():
    current = {"algo_old.yaml": {"total": 5, "prose": 2}}
    baseline = {"algo_old.yaml": {"total": 5, "prose": 2}}
    problems = check_against_baseline(current, baseline)
    assert problems == []


def test_multiple_regressions_all_reported():
    current = {
        "algo_1.yaml": {"total": 2, "prose": 2},
        "algo_2.yaml": {"total": 3, "prose": 1},
    }
    baseline = {
        "algo_1.yaml": {"total": 2, "prose": 1},
        "algo_2.yaml": {"total": 3, "prose": 1},
    }
    problems = check_against_baseline(current, baseline)
    assert len(problems) == 1
    assert "algo_1.yaml" in problems[0]


# ── Committed baseline sanity check ──────────────────────────────────────


def test_committed_baseline_matches_current_repo_state():
    """Guards against the baseline drifting out of sync with the repo
    without going through --write-baseline deliberately. If this fails,
    either a prose-condition regression slipped in without CI catching
    it, or the baseline needs regenerating after a genuine content fix."""
    import json
    from pathlib import Path

    from scripts.check_prose_conditions import ALGO_ROOT, BASELINE_PATH

    if not BASELINE_PATH.is_file():
        pytest.skip("baseline not committed yet")

    current = count_conditions(ALGO_ROOT)
    baseline_payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline = baseline_payload.get("counts", baseline_payload)
    problems = check_against_baseline(current, baseline)
    assert problems == [], (
        "Committed baseline shows a regression against the current repo "
        "state:\n  " + "\n  ".join(problems)
    )
