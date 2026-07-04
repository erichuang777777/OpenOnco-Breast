"""Algorithm routing regression snapshot.

Per docs/reviews/fable-opinion.md Section 5, Phase 2: before touching
any Algorithm `decision_tree` content (including the DEAD-class
prose-condition cleanup this phase performs), a safety net must exist
that shows *exactly* what routing changed, rather than trusting "the
prose was dead so nothing should change" without verification.

`scripts/build_routing_snapshot.py` runs two generic archetypes
("empty", "all_true" — deliberately not clinically-targeted; see that
module's docstring) against every Algorithm and snapshots
`(default_indication_id, alternative_indication_id)`. This test
compares the current repo state against the committed snapshot
(`tests/fixtures/algorithm_routing_snapshot.json`) and fails on any
diff — any PR touching a `decision_tree` must either show zero diff
here, or explicitly regenerate the snapshot and say why in the PR
description (per the fable-opinion.md Phase 2 exit criteria).
"""

from __future__ import annotations

import json

from scripts.build_routing_snapshot import (
    SNAPSHOT_PATH,
    build_snapshot,
    diff_snapshot,
)


def test_committed_snapshot_matches_current_repo_state():
    assert SNAPSHOT_PATH.is_file(), (
        "No committed routing snapshot found — run "
        "`python scripts/build_routing_snapshot.py` and commit the result."
    )
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    current = build_snapshot()
    diffs = diff_snapshot(current, committed)
    assert diffs == [], (
        "Algorithm routing changed without the snapshot being "
        "regenerated:\n  " + "\n  ".join(diffs)
    )


def test_snapshot_has_no_unexpected_errors():
    """A generate_plan() crash for any algorithm+archetype combination
    is a real bug (schema drift, missing entity), not routing noise —
    surface it distinctly from a routing diff."""
    current = build_snapshot()
    errors = {k: v["error"] for k, v in current.items() if "error" in v}
    assert errors == {}, f"generate_plan() raised for: {errors}"


def test_snapshot_covers_every_algorithm():
    """Every Algorithm entity must have both archetypes represented —
    guards against the harness silently skipping an algorithm (e.g. a
    KB-load failure that gets swallowed)."""
    from pathlib import Path

    algo_root = (
        Path(__file__).parent.parent
        / "knowledge_base" / "hosted" / "content" / "algorithms"
    )
    algo_count = len(list(algo_root.glob("*.yaml")))

    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert len(committed) == algo_count * 2, (
        f"Expected {algo_count * 2} rows (2 archetypes x {algo_count} "
        f"algorithms), found {len(committed)}"
    )
