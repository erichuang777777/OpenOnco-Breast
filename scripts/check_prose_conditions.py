#!/usr/bin/env python3
"""Prose-condition CI ratchet — stops the count from growing.

Background: `condition:` clauses in Algorithm decision trees
(`knowledge_base/hosted/content/algorithms/*.yaml`) are evaluated by
`knowledge_base/engine/redflag_eval.py::_eval_clause` as a literal
finding-key lookup. When a `condition:` is English prose (e.g. "HCV RNA
positive AND indolent presentation") instead of a real finding key, the
lookup always misses and the clause silently evaluates False — the step
falls through to its `if_false`/default branch even though it reads like
a gated clinical check. See `docs/reviews/openonco-state-audit-2026-05-17.md`
and `redflag_eval.py`'s own module docstring for the full history.

A rescan on 2026-07-04 found the count of prose conditions had *grown*
since the 2026-05-17 audit (97% of 675 conditions across 180 files, up
from 85% of 443 across 152 files) — new algorithm files were reproducing
the same broken pattern. Fixing the existing backlog is a clinical-content
change requiring CHARTER §6.1 two-reviewer sign-off; this script does not
attempt that. It only stops the backlog from growing further, which is a
pure tooling/CI change with no clinical-content implication.

Usage:
    python scripts/check_prose_conditions.py                 # check against baseline
    python scripts/check_prose_conditions.py --write-baseline  # (re)generate baseline

Exit codes:
  0 — no new prose conditions, no growth in any existing file
  1 — a new algorithm file has prose conditions, or an existing file's
      prose count increased versus the baseline
  2 — no baseline file found (run --write-baseline first)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ALGO_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "algorithms"
BASELINE_PATH = REPO_ROOT / "docs" / "audits" / "prose_condition_baseline.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _iter_clauses(node: Any):
    """Recursively yield every clause dict nested under all_of/any_of/none_of.

    A clause is a dict carrying one of `condition`/`finding`/`red_flag`
    (a leaf test) or a further `all_of`/`any_of`/`none_of` (a nested
    boolean group) — matches the shape documented in
    `knowledge_base/engine/redflag_eval.py`'s module docstring and
    `knowledge_base/schemas/algorithm.py::DecisionStep.evaluate`.
    """
    if isinstance(node, dict):
        if "condition" in node or "finding" in node or "red_flag" in node:
            yield node
        for key in ("all_of", "any_of", "none_of"):
            for child in node.get(key) or []:
                yield from _iter_clauses(child)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_clauses(item)


def count_conditions(algo_root: Path = ALGO_ROOT) -> dict[str, dict[str, int]]:
    """Return {filename: {"total": N, "prose": M}} across all algorithm YAMLs.

    `total` counts every `condition:`-bearing clause (whether prose or a
    legitimate flat finding key); `prose` counts the subset that
    `_looks_like_prose_condition` flags as unresolvable English prose.
    """
    from knowledge_base.engine.redflag_eval import _looks_like_prose_condition

    counts: dict[str, dict[str, int]] = {}
    for path in sorted(algo_root.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        total = 0
        prose = 0
        for step in doc.get("decision_tree", []) or []:
            evaluate = step.get("evaluate") or {}
            for clause in _iter_clauses(evaluate):
                cond = clause.get("condition")
                if cond is None:
                    continue
                total += 1
                if _looks_like_prose_condition(cond):
                    prose += 1
        counts[path.name] = {"total": total, "prose": prose}
    return counts


def write_baseline(counts: dict[str, dict[str, int]], path: Path = BASELINE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "Per-file condition:/prose-condition counts, committed as a CI "
            "ratchet baseline by scripts/check_prose_conditions.py. The "
            "existing backlog is grandfathered (fixing it needs CHARTER "
            "§6.1 clinical sign-off) — this file only prevents the count "
            "from growing further. Regenerate with --write-baseline only "
            "after a reviewed content change actually reduces a file's "
            "prose count; never to silence a real regression."
        ),
        "counts": counts,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check_against_baseline(
    current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]
) -> list[str]:
    """Return human-readable regression messages; empty list = pass."""
    problems: list[str] = []
    for fname, cur in sorted(current.items()):
        base = baseline.get(fname)
        if base is None:
            if cur["prose"] > 0:
                problems.append(
                    f"{fname}: new algorithm file with {cur['prose']} prose "
                    "condition(s). `condition:` clauses must reference a "
                    "real finding key, or use {finding:/threshold:} / "
                    "{red_flag: RF-X} inside all_of/any_of/none_of — see "
                    "knowledge_base/engine/redflag_eval.py's module docstring."
                )
            continue
        if cur["prose"] > base["prose"]:
            problems.append(
                f"{fname}: prose condition count increased from "
                f"{base['prose']} to {cur['prose']}. Existing prose "
                "conditions are grandfathered; new ones are not. See "
                "docs/reviews/openonco-state-audit-2026-05-17.md."
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="(Re)generate the committed baseline from the current KB state.",
    )
    parser.add_argument("--algo-root", type=Path, default=ALGO_ROOT)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    args = parser.parse_args()

    current = count_conditions(args.algo_root)

    if args.write_baseline:
        write_baseline(current, args.baseline)
        total_prose = sum(c["prose"] for c in current.values())
        total = sum(c["total"] for c in current.values())
        print(
            f"Baseline written: {args.baseline} "
            f"({total_prose}/{total} prose conditions across {len(current)} files)"
        )
        return 0

    if not args.baseline.is_file():
        print(
            f"No baseline found at {args.baseline} — run with "
            "--write-baseline first.",
            file=sys.stderr,
        )
        return 2

    baseline_payload = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline = baseline_payload.get("counts", baseline_payload)
    problems = check_against_baseline(current, baseline)

    if problems:
        print("Prose-condition ratchet FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1

    total_prose = sum(c["prose"] for c in current.values())
    baseline_total = sum(c["prose"] for c in baseline.values())
    trend = "improved" if total_prose < baseline_total else "unchanged"
    print(
        f"Prose-condition ratchet OK: {total_prose} prose conditions "
        f"(baseline: {baseline_total}, {trend})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
