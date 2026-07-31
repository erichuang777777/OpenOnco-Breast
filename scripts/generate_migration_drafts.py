#!/usr/bin/env python3
"""Phase 3 (fable-opinion.md Section 5) — generate per-disease migration
draft documents for the 554 routing-changing prose conditions
(structural_class in SOLE_ANY/SOLE_ALL/MIXED_ALL).

**Produces review documents only. Never touches
`knowledge_base/hosted/content/`.** Every one of these 554 conditions,
unlike the 100 DEAD-class ones, changes actual algorithm routing when
fixed -- CHARTER Sec 6.1 requires two Clinical Co-Lead sign-offs before
any such change merges, and all three Co-Lead seats are currently open
(specs/CLINICAL_LEADS.md). This script's output is meant to make that
future review fast, not to bypass it.

One markdown file per disease under
`docs/audits/migration_drafts/<disease_id>.md`, containing, per
affected algorithm file:
  - Whether the file's step 1 is entirely prose (highest-severity flag
    -- every patient currently falls through to that algorithm's
    default_indication regardless of presentation).
  - Each routing-changing condition: current text, structural class,
    confidence tier, and (for HIGH_CONFIDENCE_RENAME rows) the Phase 1
    tool's proposed structured rewrite.
  - An explicit call-out for NEEDS_NEW_FINDING / NEEDS_CLINICAL_JUDGMENT
    rows naming exactly what's missing, so a reviewer isn't left
    guessing.

Plus a top-level `docs/audits/migration_drafts/README.md` index,
ranked by severity (step-1-fully-prose files first).

Usage:
    python scripts/generate_migration_drafts.py
"""

from __future__ import annotations

import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ALGO_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "algorithms"
DISEASE_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "diseases"
QUEUE_CSV = REPO_ROOT / "docs" / "audits" / "algorithm_condition_migration_queue.csv"
OUTPUT_ROOT = REPO_ROOT / "docs" / "audits" / "migration_drafts"

_ROUTING_CHANGING = {"SOLE_ANY", "SOLE_ALL", "MIXED_ALL"}

_CONFIDENCE_LABEL = {
    "HIGH_CONFIDENCE_RENAME": "Likely mechanical rename — still needs a clinician's confirmation "
                                "(polarity, threshold, and any dropped qualifier are not checked).",
    "NEEDS_NEW_FINDING": "No candidate finding key exists in the KB — needs a new "
                          "biomarker/RedFlag/questionnaire field before this can route on anything.",
    "NEEDS_CLINICAL_JUDGMENT": "No gene/biomarker-shaped token found — this is vague descriptive "
                                "prose that needs a clinician to define an operational threshold.",
}


def _disease_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for path in glob.glob(str(DISEASE_ROOT / "*.yaml")):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        did = doc.get("id")
        if did:
            names[did] = (doc.get("names") or {}).get("preferred") or did
    return names


def _algorithm_disease_map() -> dict[str, str]:
    """{algorithm_filename: disease_id}"""
    mapping: dict[str, str] = {}
    for path in glob.glob(str(ALGO_ROOT / "*.yaml")):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        disease_id = doc.get("applicable_to_disease")
        if disease_id:
            mapping[Path(path).name] = disease_id
    return mapping


def _file_step1_fully_prose(filename: str, rows_by_file: dict[str, list[dict]]) -> bool:
    """True if every condition-bearing clause in step 1 of this file is
    a routing-changing prose clause (SOLE_ANY/SOLE_ALL/MIXED_ALL) —
    i.e. this algorithm falls through to its default for every patient
    regardless of presentation. Best-effort: only knows about clauses
    already flagged prose by Phase 1; doesn't re-parse the YAML."""
    step1_rows = [r for r in rows_by_file.get(filename, []) if r["step"] == "1"]
    return bool(step1_rows) and all(
        r["structural_class"] in _ROUTING_CHANGING for r in step1_rows
    )


def load_routing_changing_rows(queue_csv: Path = QUEUE_CSV) -> dict[str, list[dict]]:
    by_file: dict[str, list[dict]] = defaultdict(list)
    with queue_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["structural_class"] in _ROUTING_CHANGING:
                by_file[row["file"]].append(row)
    return dict(by_file)


def _step_sort_key(step: str) -> tuple[int, str]:
    """Steps are usually plain integers but occasionally alphanumeric
    branch labels like "3a" (Algorithm.decision_tree[].step is typed
    Union[int, str] in the schema). Sort numeric prefix first, then
    the full string, so "3a" sorts near "3" rather than crashing on
    int(step)."""
    prefix = ""
    for ch in step:
        if ch.isdigit():
            prefix += ch
        else:
            break
    return (int(prefix) if prefix else 0, step)


def _render_row(row: dict) -> str:
    lines = [
        f"- **`{row['clause_path']}`** (step {row['step']}, {row['structural_class']}): "
        f"`condition: \"{row['condition_text']}\"`",
        f"  - Confidence: **{row['confidence']}** — "
        f"{_CONFIDENCE_LABEL.get(row['confidence'], '')}",
    ]
    if row["confidence"] == "HIGH_CONFIDENCE_RENAME" and row["proposed_clause"]:
        lines.append(f"  - Proposed rewrite (unreviewed): `{row['proposed_clause']}`")
    if row["candidate_finding_keys"]:
        lines.append(f"  - Candidate finding key(s): `{row['candidate_finding_keys']}`")
    return "\n".join(lines)


def generate_drafts(
    queue_csv: Path = QUEUE_CSV,
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, int]:
    """Write one markdown file per disease + an index. Returns
    {disease_id: condition_count} for the caller to report."""
    rows_by_file = load_routing_changing_rows(queue_csv)
    algo_to_disease = _algorithm_disease_map()
    disease_names = _disease_names()

    by_disease: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for filename, rows in rows_by_file.items():
        disease_id = algo_to_disease.get(filename, "UNKNOWN-DISEASE")
        by_disease[disease_id][filename] = rows

    output_root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    severity: list[tuple[bool, str, int]] = []  # (any_step1_fully_prose, disease_id, count)

    for disease_id, files in sorted(by_disease.items()):
        display_name = disease_names.get(disease_id, disease_id)
        total = sum(len(rows) for rows in files.values())
        counts[disease_id] = total

        lines = [
            f"# Migration draft — {display_name} ({disease_id})",
            "",
            "**Draft only. Not applied. Every clause below still needs a Clinical "
            "Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real "
            "Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and "
            "`docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even "
            "a routing-snapshot-clean change isn't sufficient proof of safety on its "
            "own in this repo.",
            "",
        ]

        any_step1_fully_prose = False
        for filename in sorted(files):
            rows = files[filename]
            step1_broken = _file_step1_fully_prose(filename, rows_by_file)
            any_step1_fully_prose = any_step1_fully_prose or step1_broken
            flag = " ⚠️ **step 1 entirely prose — every patient falls through to default_indication**" if step1_broken else ""
            lines.append(f"## `{filename}`{flag}")
            lines.append("")
            for row in sorted(rows, key=lambda r: (_step_sort_key(r["step"]), r["clause_path"])):
                lines.append(_render_row(row))
            lines.append("")

        (output_root / f"{disease_id}.md").write_text("\n".join(lines), encoding="utf-8")
        severity.append((any_step1_fully_prose, disease_id, total))

    # Index, ranked: step-1-fully-prose diseases first (highest impact —
    # per fable-opinion.md, 99/180 files corpus-wide are this severe),
    # then by condition count descending.
    severity.sort(key=lambda t: (not t[0], -t[2]))
    index_lines = [
        "# Phase 3 migration drafts — index",
        "",
        "Per-disease draft documents for the 554 routing-changing prose "
        "conditions (structural_class SOLE_ANY/SOLE_ALL/MIXED_ALL from "
        "`docs/audits/algorithm_condition_migration_queue.csv`). Draft "
        "only -- see `docs/reviews/fable-opinion.md` Phase 3 for the "
        "process these need to go through before merging.",
        "",
        "Ranked: diseases with at least one algorithm whose step 1 is "
        "entirely prose (⚠️, highest impact) first, then by total "
        "condition count.",
        "",
        "| Disease | Conditions | Step-1-fully-prose? |",
        "|---|---|---|",
    ]
    for has_flag, disease_id, total in severity:
        display_name = disease_names.get(disease_id, disease_id)
        flag = "⚠️ yes" if has_flag else "no"
        index_lines.append(f"| [{display_name}](./{disease_id}.md) ({disease_id}) | {total} | {flag} |")

    (output_root / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    return counts


def main() -> int:
    counts = generate_drafts()
    print(f"Wrote {len(counts)} per-disease draft files + index to {OUTPUT_ROOT}")
    print(f"Total routing-changing conditions covered: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
