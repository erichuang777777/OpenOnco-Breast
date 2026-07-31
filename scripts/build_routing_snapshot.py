#!/usr/bin/env python3
"""Algorithm routing snapshot — regression safety net for Phase 2 of
docs/reviews/fable-opinion.md Section 5.

Runs `generate_plan()` against every Algorithm entity with two generic,
deliberately non-clinical archetypes:

  - "empty":     no findings known at all (disease + line only).
  - "all_true":  every finding key referenced by a *real* (non-prose)
                 clause in that algorithm's decision tree set to a
                 positive/truthy value.

These are NOT attempts to construct "the correct patient for
indication X" — doing that would require clinical judgment (which
findings should route to which regimen) that this tool deliberately
does not attempt; see fable-opinion.md's hard-line guardrails. They
exist purely to exercise each algorithm's decision tree with a
reproducible, mechanical input and snapshot whatever the engine
currently outputs, so a later change to a `decision_tree` shows up as
an explicit, reviewable diff instead of a silent behavior change.

When multiple Algorithm entities share the same (disease, line) —
disambiguated in production by `applicable_to_disease_state` — this
script resolves the patient's `disease_state` to the algorithm under
test and verifies the engine actually selected it. If a different
(state-agnostic) algorithm wins instead, the row is marked
`"unreachable_in_isolation"` rather than silently attributing another
algorithm's output to the wrong ID.

Usage:
    python scripts/build_routing_snapshot.py            # write the snapshot
    python scripts/build_routing_snapshot.py --check     # compare only, exit 1 on diff
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
SNAPSHOT_PATH = REPO_ROOT / "tests" / "fixtures" / "algorithm_routing_snapshot.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _collect_resolvable_finding_keys(algorithm: dict) -> set[str]:
    """Every finding key referenced by a real (non-prose) clause
    anywhere in this algorithm's decision tree."""
    from knowledge_base.engine.redflag_eval import _looks_like_prose_condition

    keys: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "finding" in node:
                keys.add(node["finding"])
            cond = node.get("condition")
            if cond and not _looks_like_prose_condition(cond):
                keys.add(cond)
            for key in ("all_of", "any_of", "none_of"):
                for child in node.get(key) or []:
                    walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for step in algorithm.get("decision_tree", []) or []:
        walk(step.get("evaluate") or {})
    return keys


def _archetypes_for_algorithm(algorithm: dict) -> dict[str, dict]:
    disease_id = algorithm["applicable_to_disease"]
    line = algorithm["applicable_to_line_of_therapy"]
    disease_state = algorithm.get("applicable_to_disease_state")

    base: dict[str, Any] = {
        "patient_id": "SNAPSHOT-TEST",
        "disease": {"id": disease_id},
        "line_of_therapy": line,
        "demographics": {},
        "findings": {},
        "biomarkers": {},
    }
    if disease_state:
        base["disease_state"] = disease_state

    keys = _collect_resolvable_finding_keys(algorithm)
    return {
        "empty": {**base, "findings": {}},
        "all_true": {**base, "findings": {k: True for k in keys}},
    }


def build_snapshot(kb_root: Path = KB_ROOT) -> dict[str, dict]:
    from knowledge_base.engine import generate_plan
    from knowledge_base.validation.loader import clear_load_cache, load_content

    clear_load_cache()
    result = load_content(kb_root)
    algorithms = {
        eid: info["data"]
        for eid, info in result.entities_by_id.items()
        if info["type"] == "algorithms"
    }

    snapshot: dict[str, dict] = {}
    for algo_id, algo in sorted(algorithms.items()):
        for archetype_name, patient in _archetypes_for_algorithm(algo).items():
            row_key = f"{algo_id}::{archetype_name}"
            try:
                plan_result = generate_plan(patient, kb_root=kb_root)
            except Exception as exc:  # pylint: disable=broad-except
                snapshot[row_key] = {"error": f"{type(exc).__name__}: {exc}"}
                continue

            if plan_result.algorithm_id != algo_id:
                # A different (state-agnostic) algorithm won the same
                # (disease, line) slot — this row can't isolate algo_id's
                # own behavior, so don't misattribute another
                # algorithm's routing to it.
                snapshot[row_key] = {
                    "unreachable_in_isolation": True,
                    "actual_algorithm_selected": plan_result.algorithm_id,
                }
                continue

            snapshot[row_key] = {
                "default_indication_id": plan_result.default_indication_id,
                "alternative_indication_id": plan_result.alternative_indication_id,
            }
    return snapshot


def write_snapshot(snapshot: dict[str, dict], path: Path = SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def diff_snapshot(
    current: dict[str, dict], committed: dict[str, dict]
) -> list[str]:
    """Return a list of human-readable diffs; empty = no routing change."""
    diffs: list[str] = []
    all_keys = sorted(set(current) | set(committed))
    for key in all_keys:
        cur = current.get(key)
        base = committed.get(key)
        if cur != base:
            diffs.append(f"{key}: {base!r} -> {cur!r}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--check", action="store_true",
        help="Compare against the committed snapshot instead of writing it.",
    )
    parser.add_argument("--kb-root", type=Path, default=KB_ROOT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args()

    current = build_snapshot(args.kb_root)

    if not args.check:
        write_snapshot(current, args.snapshot)
        print(f"Wrote {len(current)} rows to {args.snapshot}")
        return 0

    if not args.snapshot.is_file():
        print(f"No snapshot found at {args.snapshot} — run without --check first.", file=sys.stderr)
        return 2

    committed = json.loads(args.snapshot.read_text(encoding="utf-8"))
    diffs = diff_snapshot(current, committed)
    if diffs:
        print("Routing snapshot diff detected:")
        for d in diffs:
            print(f"  - {d}")
        return 1
    print(f"Routing snapshot OK: {len(current)} rows unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
