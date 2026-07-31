#!/usr/bin/env python3
"""Phase 2 (fable-opinion.md Section 5) — remove provably-dead prose
`condition:` clauses from Algorithm YAML files.

Scope is deliberately narrow: only rows the Phase 1 audit
(`scripts/audit_prose_conditions.py`) classified `structural_class ==
"DEAD"` — a prose clause sitting inside an `any_of` alongside a
*working* sibling clause (`finding:`/`red_flag:`/non-prose
`condition:`). Removing it cannot change the `any_of`'s result: the
working sibling already determines the OR whenever it matters. This is
the only prose-condition cleanup this tool performs without clinical
review — every other structural class (SOLE_ANY/SOLE_ALL/MIXED_ALL)
changes actual routing and needs CHARTER Sec 6.1 sign-off, per
fable-opinion.md's hard-line guardrails.

Safety design: uses the Phase 1 CSV's `clause_path`
(e.g. "all_of[1].any_of[3]") to navigate to the *exact* list position
via ruamel.yaml's round-trip loader (preserves comments/formatting/
quote style -- avoids reformatting-noise in the diff), rather than
matching by condition text alone. Text-only matching is provably
unsafe here: 14 (file, condition_text) pairs in the corpus repeat the
same prose string at more than one position in the same file, some
DEAD and some not.

Before deleting, each clause is verified to actually be
`{"condition": <expected text>}` at that exact path -- if the file has
drifted since the CSV was generated, the row is skipped and reported,
never guessed at.

*** KNOWN GAP, found the hard way (2026-07-04) — do not re-run this
*** against real content without addressing it first:

"DEAD" only proves the *any_of* has a working sibling in the general
case. It does NOT prove no caller ever resolves the prose text itself
-- some patient fixtures in this repo set the literal prose string as
a finding key directly (a known workaround; see
docs/reviews/openonco-state-audit-2026-05-17.md and
tests/test_esophageal_1l_algorithm.py, which sets
`{"ESCC CPS >=1": True}`). Applying this script's first version to
`algo_esoph_metastatic_1l.yaml` removed exactly that clause and broke
`test_escc_cps_positive_chemo_sparing_routes_to_ipi_nivo` -- a real
routing change that the two-archetype routing snapshot
(`scripts/build_routing_snapshot.py`) did not catch, because its
generic archetypes never happen to set a literal prose string as a
finding key.

Before applying again: run the FULL existing test suite (not just the
routing snapshot) after each file's edit -- or, more conservatively,
after each individual clause removal -- and revert immediately on any
failure. Do not treat a clean routing-snapshot diff alone as
sufficient proof of safety for this specific class of change.

The 2026-07-04 attempt was reverted in full (100 removals across 41
files) after this was discovered; nothing from that attempt is applied
to the current tree.

Usage:
    python scripts/apply_dead_condition_cleanup.py            # apply
    python scripts/apply_dead_condition_cleanup.py --dry-run   # report only
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
ALGO_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "algorithms"
QUEUE_CSV = REPO_ROOT / "docs" / "audits" / "algorithm_condition_migration_queue.csv"

_PATH_SEGMENT = re.compile(r"^(\w+)\[(\d+)\]$")


def _parse_clause_path(clause_path: str) -> list[tuple[str, int]]:
    segments = []
    for part in clause_path.split("."):
        m = _PATH_SEGMENT.match(part)
        if not m:
            raise ValueError(f"Unrecognized clause_path segment: {part!r}")
        segments.append((m.group(1), int(m.group(2))))
    return segments


def _locate_container(evaluate_node: Any, segments: list[tuple[str, int]]):
    """Navigate to (containing_list, index_to_delete) for the clause at
    the end of `segments`, per the last (key, index) pair."""
    node = evaluate_node
    for key, idx in segments[:-1]:
        node = node[key][idx]
    last_key, last_idx = segments[-1]
    return node[last_key], last_idx


def load_dead_rows(queue_csv: Path = QUEUE_CSV) -> dict[str, list[dict]]:
    """Return {filename: [row, ...]} for every DEAD-class row, sorted
    per-file by clause index descending (so deleting one clause never
    shifts the index of another clause not yet processed in the same
    list)."""
    by_file: dict[str, list[dict]] = {}
    with queue_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["structural_class"] == "DEAD":
                by_file.setdefault(row["file"], []).append(row)

    for fname, rows in by_file.items():
        rows.sort(
            key=lambda r: _parse_clause_path(r["clause_path"])[-1][1],
            reverse=True,
        )
    return by_file


def apply_cleanup(
    algo_root: Path = ALGO_ROOT,
    queue_csv: Path = QUEUE_CSV,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Returns {filename: [messages]} — one entry per file touched or
    skipped, for reporting."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't rewrap long lines

    by_file = load_dead_rows(queue_csv)
    report: dict[str, list[str]] = {}

    for fname, rows in sorted(by_file.items()):
        path = algo_root / fname
        messages: list[str] = []
        doc = yaml.load(path.read_text(encoding="utf-8"))
        steps_by_number = {step["step"]: step for step in doc.get("decision_tree", [])}

        removed = 0
        for row in rows:
            step_key = row["step"]
            # CSV stores step as a string; YAML keys may be int or str.
            step = steps_by_number.get(step_key) or steps_by_number.get(int(step_key))
            if step is None:
                messages.append(
                    f"SKIP step {step_key} not found (clause_path={row['clause_path']})"
                )
                continue

            segments = _parse_clause_path(row["clause_path"])
            try:
                container, idx = _locate_container(step["evaluate"], segments)
            except (KeyError, IndexError, TypeError) as exc:
                messages.append(
                    f"SKIP step {step_key} clause_path={row['clause_path']} "
                    f"navigation failed: {exc}"
                )
                continue

            actual = container[idx]
            expected_text = row["condition_text"]
            if not (isinstance(actual, dict) and actual.get("condition") == expected_text):
                messages.append(
                    f"SKIP step {step_key} clause_path={row['clause_path']} — "
                    f"file drifted: expected condition={expected_text!r}, "
                    f"found {actual!r}"
                )
                continue

            if not dry_run:
                del container[idx]
            removed += 1
            messages.append(f"OK removed step {step_key} clause_path={row['clause_path']}")

        if removed and not dry_run:
            yaml.dump(doc, path)

        report[fname] = messages

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--algo-root", type=Path, default=ALGO_ROOT)
    parser.add_argument("--queue", type=Path, default=QUEUE_CSV)
    args = parser.parse_args()

    report = apply_cleanup(args.algo_root, args.queue, dry_run=args.dry_run)

    total_ok = 0
    total_skip = 0
    for fname, messages in report.items():
        for msg in messages:
            print(f"{fname}: {msg}")
            if msg.startswith("OK"):
                total_ok += 1
            else:
                total_skip += 1

    print(f"\n{'[dry-run] ' if args.dry_run else ''}{total_ok} removed, {total_skip} skipped")
    return 1 if total_skip else 0


if __name__ == "__main__":
    sys.exit(main())
