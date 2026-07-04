"""Phase 3 migration-draft generator — unit tests.

Module: scripts/generate_migration_drafts.py
Context: docs/reviews/fable-opinion.md Phase 3 — produces per-disease
review documents for the 554 routing-changing prose conditions.
Draft-only; asserts nothing under knowledge_base/ is ever touched.
"""

from __future__ import annotations

from scripts.generate_migration_drafts import (
    _file_step1_fully_prose,
    _render_row,
    _step_sort_key,
    load_routing_changing_rows,
)


def _row(step="1", clause_path="any_of[0]", structural_class="SOLE_ANY",
         confidence="NEEDS_CLINICAL_JUDGMENT", condition_text="some prose",
         proposed_clause="", candidate_finding_keys=""):
    return {
        "step": step,
        "clause_path": clause_path,
        "structural_class": structural_class,
        "confidence": confidence,
        "condition_text": condition_text,
        "proposed_clause": proposed_clause,
        "candidate_finding_keys": candidate_finding_keys,
    }


def test_step_sort_key_handles_plain_integers():
    assert _step_sort_key("1") < _step_sort_key("2") < _step_sort_key("10")


def test_step_sort_key_handles_alphanumeric_branch_labels():
    """Algorithm.decision_tree[].step is typed Union[int, str] --
    branch labels like "3a" must not crash the sort (regression test
    for the ValueError this caused against the real corpus)."""
    key = _step_sort_key("3a")
    assert key[0] == 3


def test_render_row_includes_proposed_clause_for_high_confidence():
    row = _row(
        confidence="HIGH_CONFIDENCE_RENAME",
        condition_text="HCV RNA positive",
        proposed_clause='{finding: "hcv_rna"}',
        candidate_finding_keys="hcv_rna",
    )
    out = _render_row(row)
    assert "HIGH_CONFIDENCE_RENAME" in out
    assert '{finding: "hcv_rna"}' in out
    assert "hcv_rna" in out


def test_render_row_omits_proposed_clause_for_low_confidence():
    row = _row(confidence="NEEDS_CLINICAL_JUDGMENT", proposed_clause="")
    out = _render_row(row)
    assert "Proposed rewrite" not in out


def test_load_routing_changing_rows_excludes_dead(tmp_path):
    csv_path = tmp_path / "queue.csv"
    csv_path.write_text(
        "file,step,clause_path,condition_text,structural_class,confidence,"
        "proposed_clause,candidate_finding_keys\n"
        "a.yaml,1,any_of[0],text1,DEAD,HIGH_CONFIDENCE_RENAME,,\n"
        "a.yaml,1,any_of[1],text2,SOLE_ANY,NEEDS_CLINICAL_JUDGMENT,,\n"
        "b.yaml,2,all_of[0],text3,MIXED_ALL,NEEDS_NEW_FINDING,,\n",
        encoding="utf-8",
    )
    by_file = load_routing_changing_rows(csv_path)
    assert "a.yaml" in by_file
    assert len(by_file["a.yaml"]) == 1  # DEAD row excluded
    assert by_file["a.yaml"][0]["condition_text"] == "text2"
    assert "b.yaml" in by_file


def test_file_step1_fully_prose_true_when_all_step1_rows_routing_changing():
    rows_by_file = {
        "a.yaml": [
            _row(step="1", structural_class="SOLE_ANY"),
            _row(step="1", structural_class="SOLE_ALL"),
            _row(step="2", structural_class="DEAD"),  # different step, ignored
        ]
    }
    assert _file_step1_fully_prose("a.yaml", rows_by_file) is True


def test_file_step1_fully_prose_false_when_no_step1_rows():
    rows_by_file = {"a.yaml": [_row(step="2", structural_class="SOLE_ANY")]}
    assert _file_step1_fully_prose("a.yaml", rows_by_file) is False


def test_generate_drafts_never_writes_under_knowledge_base(tmp_path):
    """The generator must only ever write under its own output_root —
    never touch knowledge_base/hosted/content/ regardless of arguments."""
    import scripts.generate_migration_drafts as mod

    output_root = tmp_path / "drafts"
    counts = mod.generate_drafts(output_root=output_root)

    assert output_root.is_dir()
    assert (output_root / "README.md").is_file()
    assert sum(counts.values()) > 0

    # No file under output_root path components touches knowledge_base.
    for path in output_root.rglob("*"):
        assert "knowledge_base" not in str(path)


def test_generate_drafts_total_matches_committed_queue_csv():
    """The generator's total row count must match the CSV's
    routing-changing subset exactly -- a drift here would mean the
    generator and the Phase 1 tool disagree about what's in scope."""
    import csv as csv_module

    import scripts.generate_migration_drafts as mod

    counts = mod.generate_drafts()
    with mod.QUEUE_CSV.open(encoding="utf-8") as f:
        expected = sum(
            1 for row in csv_module.DictReader(f)
            if row["structural_class"] in ("SOLE_ANY", "SOLE_ALL", "MIXED_ALL")
        )
    assert sum(counts.values()) == expected
