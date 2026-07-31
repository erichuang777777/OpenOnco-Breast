#!/usr/bin/env python3
"""Phase 1 triage tool — classify every prose `condition:` clause in
Algorithm decision trees, per docs/reviews/fable-opinion.md Section 5.

This is a **best-effort triage aid**, not an authoritative or auto-
mergeable answer. It exists to turn "654 broken strings" into a
prioritized, human-reviewable queue instead of an undifferentiated
pile. Every row still needs a real person (eventually a Clinical
Co-Lead, per CHARTER §6.1) to confirm before anything gets merged.

Classification has two independent axes:

1. `structural_class` — does fixing this specific clause change what
   the engine actually does, or is it already inert?
   - DEAD:       inside an `any_of` that has a working sibling clause
                 (finding:/red_flag:/non-prose condition:) — the OR
                 already resolves correctly regardless of this clause.
   - SOLE_ANY:   inside an `any_of` where every clause is prose —
                 the OR is stuck at False.
   - SOLE_ALL:   inside an `all_of` where every clause is prose —
                 the AND is stuck at False.
   - MIXED_ALL:  inside an `all_of` mixing prose with working clauses
                 — the AND is still stuck at False (one False clause
                 fails the whole AND), so this is just as broken as
                 SOLE_ALL, just easier to misread as "mostly working."

2. `confidence` — how much of the prose maps onto a finding key that
   already exists somewhere in the KB (biomarker IDs, RedFlag trigger
   `finding:` keys, `FINDING_ALIASES`, other algorithms' working
   `finding:`/`condition:` clauses):
   - HIGH_CONFIDENCE_RENAME: every clause-like segment of the prose
     (split on " and "/" or ") matches a known finding key by token
     overlap. Still means "worth a human's first look", never
     "auto-mergeable" — see the honesty flag in fable-opinion.md.
   - NEEDS_NEW_FINDING: at least one segment has no candidate match
     but contains a gene/biomarker-shaped token (ALL-CAPS, e.g.
     TET2/DNMT3A) — the KB is missing that finding/biomarker entirely.
   - NEEDS_CLINICAL_JUDGMENT: at least one segment has no candidate
     match and no gene-shaped token (vague descriptive prose, e.g.
     "significant comorbidity burden") — needs a clinician to define
     an operational threshold, not just a rename.

Usage:
    python scripts/audit_prose_conditions.py
        # writes docs/audits/algorithm_condition_migration_queue.csv

    python scripts/audit_prose_conditions.py --output FILE.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ALGO_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "algorithms"
BIOMARKER_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "biomarkers"
REDFLAG_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "redflags"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "audits" / "algorithm_condition_migration_queue.csv"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ── Tokenization (mirrors the spirit of trial_outlook._biomarker_tokens,
#    but tuned for finding-key text rather than biomarker phrases) ───────

_STOPWORDS = {
    "positive", "negative", "documented", "present", "confirmed", "known",
    "detected", "measurable", "accessible", "preferred", "naive",
    "status", "the", "a", "an", "of", "for", "to", "no", "not",
    "required", "eligible", "candidate", "typical", "signature",
}

# Gene/biomarker-shaped token: all-caps (optionally with digits), 2+
# chars — TET2, DNMT3A, IDH2, KIT, EGFR. Used to distinguish "this needs
# a new biomarker" from "this needs a clinical judgment call."
_GENE_TOKEN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


def _tokenize(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", " ", text)
    return {
        t.lower() for t in cleaned.split()
        if t.lower() not in _STOPWORDS and len(t) > 1
    }


def _gene_like_tokens(text: str) -> list[str]:
    """Raw (not lowercased) all-caps tokens in the original text —
    used to flag "this looks like a named gene/biomarker with no KB
    entry" versus "this is just vague prose."""
    raw_tokens = re.findall(r"[A-Za-z0-9]+", text)
    return [t for t in raw_tokens if _GENE_TOKEN.match(t)]


# Matches an explicit slash/comma-separated list of 2+ gene-shaped
# tokens, e.g. "TET2/DNMT3A/IDH2" or "BRCA1, BRCA2". Deliberately
# narrower than "any 2+ all-caps tokens in the segment" — clinical
# abbreviation *pairs* like "ECOG PS" or "PD-L1 CPS" are two tokens
# describing one concept, not an enumerated list of alternatives, and
# must not trip the "single-gene match can't cover this" safeguard
# below.
_GENE_LIST = re.compile(
    r"\b[A-Z][A-Z0-9]{1,9}(?:\s*[/,]\s*[A-Z][A-Z0-9]{1,9})+\b"
)


def _explicit_gene_list_tokens(text: str) -> list[str]:
    """Gene-shaped tokens that appear inside an explicit slash/comma
    list (see `_GENE_LIST`). Empty when the segment has no such list,
    even if it separately contains loose all-caps abbreviations."""
    tokens: list[str] = []
    for match in _GENE_LIST.finditer(text):
        tokens.extend(t.strip() for t in re.split(r"[/,]", match.group()) if t.strip())
    return tokens


def _split_segments(condition: str) -> list[str]:
    """Split a compound condition on " and "/" or " (case-insensitive)
    into independently-matchable segments. A condition with no
    connective is returned as a single segment."""
    parts = re.split(r"\s+(?:and|or)\s+", condition, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


# ── Candidate finding-key registry ───────────────────────────────────────


def _iter_clauses(node: Any):
    if isinstance(node, dict):
        if "condition" in node or "finding" in node or "red_flag" in node:
            yield node
        for key in ("all_of", "any_of", "none_of"):
            for child in node.get(key) or []:
                yield from _iter_clauses(child)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_clauses(item)


def build_candidate_registry() -> dict[str, set[str]]:
    """Return {candidate_key_string: token_set} for every known-real
    finding key in the KB — biomarker IDs, RedFlag trigger `finding:`
    keys, `FINDING_ALIASES` entries, and other algorithms' working
    (non-prose) `finding:`/`condition:` clauses."""
    from knowledge_base.engine.redflag_eval import (
        FINDING_ALIASES,
        _looks_like_prose_condition,
    )

    candidates: dict[str, set[str]] = {}

    def _add(key: object) -> None:
        if isinstance(key, str) and key:
            candidates.setdefault(key, _tokenize(key))

    for path in glob.glob(str(BIOMARKER_ROOT / "*.yaml")):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        _add(doc.get("id"))

    for path in glob.glob(str(REDFLAG_ROOT / "*.yaml")):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        for clause in _iter_clauses(doc.get("trigger") or {}):
            _add(clause.get("finding"))

    for alias_key, alias_values in FINDING_ALIASES.items():
        _add(alias_key)
        for v in alias_values:
            _add(v)

    for path in glob.glob(str(ALGO_ROOT / "*.yaml")):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        for step in doc.get("decision_tree", []) or []:
            for clause in _iter_clauses(step.get("evaluate") or {}):
                _add(clause.get("finding"))
                cond = clause.get("condition")
                if cond and not _looks_like_prose_condition(cond):
                    _add(cond)

    return candidates


# Minimum fraction of a segment's substantive tokens that the matched
# candidate must account for. Without this, a long descriptive segment
# ("Aggressive histology suspected at relapse (rapid growth, B-symptoms,
# LDH raised, extranodal sites)") gets spuriously "resolved" by a single
# real finding key buried in it (b_symptoms_present) even though that
# key captures only a fragment of a genuinely multi-criteria clinical
# description. 0.4 is a deliberately conservative floor -- tuned against
# known-good matches like "No severe peripheral neuropathy (Grade >=2)"
# -> peripheral_neuropathy_grade (ratio 0.75) staying accepted, and
# known-bad matches like the histology example (ratio ~0.2) getting
# rejected.
_MIN_COVERAGE_RATIO = 0.4


def _best_match(segment_tokens: set[str], registry: dict[str, set[str]]) -> Optional[str]:
    """Return the candidate key whose own tokens are a (non-empty)
    subset of the segment's tokens AND cover at least
    `_MIN_COVERAGE_RATIO` of the segment's substantive content,
    preferring the most specific (largest-token-set) match when more
    than one qualifies.

    A subset match alone means every concept in the candidate key is
    actually present in the segment text -- not just a loose overlap --
    so a generic "IDH2" segment does NOT match a variant-specific
    "BIO-IDH2-R140Q" candidate (whose tokens include "r140q", absent
    from the segment). The coverage-ratio floor additionally guards
    against the candidate being a small fragment of a much longer,
    more complex segment (see module-level note above).
    """
    if not segment_tokens:
        return None
    best: Optional[str] = None
    best_size = 0
    for key, key_tokens in registry.items():
        if not key_tokens:
            continue
        if key_tokens <= segment_tokens and len(key_tokens) > best_size:
            coverage = len(key_tokens) / len(segment_tokens)
            if coverage < _MIN_COVERAGE_RATIO:
                continue
            best = key
            best_size = len(key_tokens)
    return best


def classify_confidence(
    condition: str, registry: dict[str, set[str]]
) -> tuple[str, list[str]]:
    """Return (confidence, matched_or_missing_candidates)."""
    segments = _split_segments(condition)
    matches: list[str] = []
    unresolved: list[str] = []
    for seg in segments:
        seg_tokens = _tokenize(seg)
        seg_gene_list = _explicit_gene_list_tokens(seg)
        match = _best_match(seg_tokens, registry)
        # A segment naming an explicit slash/comma list of 2+ distinct
        # genes (e.g. "TET2/DNMT3A/IDH2") is NOT resolved by a candidate
        # covering only one of them — matching "idh2_status"
        # (tokens={"idh2"}) against that segment would otherwise look
        # like a full resolution while silently dropping TET2 and
        # DNMT3A. Require the candidate to be at least as specific as
        # the number of genes actually enumerated. Uses the narrower
        # explicit-list detector (not "any 2+ all-caps tokens") so a
        # clinical abbreviation pair like "ECOG PS" doesn't trip this.
        if match and len(seg_gene_list) > 1 and len(registry[match]) < len(seg_gene_list):
            match = None
        if match:
            matches.append(match)
        else:
            unresolved.append(seg)

    if not unresolved:
        return "HIGH_CONFIDENCE_RENAME", matches

    has_gene_token = any(_gene_like_tokens(seg) for seg in unresolved)
    if has_gene_token:
        return "NEEDS_NEW_FINDING", matches
    return "NEEDS_CLINICAL_JUDGMENT", matches


def propose_clause(condition: str, matches: list[str]) -> str:
    """Best-effort structured rewrite for HIGH_CONFIDENCE_RENAME rows.
    Never used automatically -- always human-reviewed before landing
    in a real Algorithm YAML (see fable-opinion.md Section 4)."""
    segments = _split_segments(condition)
    joiner = "all_of" if " and " in condition.lower() else "any_of"
    if len(segments) <= 1 or len(matches) <= 1:
        return f'{{finding: "{matches[0]}"}}' if matches else ""
    clauses = ", ".join(f'{{finding: "{m}"}}' for m in matches)
    return f"{{{joiner}: [{clauses}]}}"


# ── Structural classification ────────────────────────────────────────────


def _clause_is_working(clause: dict, is_prose) -> bool:
    if "red_flag" in clause or "finding" in clause:
        return True
    if "condition" in clause:
        return not is_prose(clause["condition"])
    for key in ("all_of", "any_of", "none_of"):
        if key in clause:
            return any(_clause_is_working(c, is_prose) for c in clause[key])
    return False


def _classify_structural(group_type: str, has_working_sibling: bool) -> str:
    if group_type == "any_of":
        return "DEAD" if has_working_sibling else "SOLE_ANY"
    # all_of and none_of: any False clause (including a misresolved
    # prose clause) breaks the whole group regardless of siblings.
    return "MIXED_ALL" if has_working_sibling else "SOLE_ALL"


def _walk_group(node: Any, path: str, is_prose, rows_out: list[dict]) -> None:
    """Recursively walk a decision-tree `evaluate` node, emitting one
    row per prose `condition:` clause found, classified against its
    immediate parent group."""
    if not isinstance(node, dict):
        return
    for group_type in ("all_of", "any_of", "none_of"):
        children = node.get(group_type)
        if not children:
            continue
        for i, child in enumerate(children):
            child_path = f"{path}.{group_type}[{i}]" if path else f"{group_type}[{i}]"
            if isinstance(child, dict) and "condition" in child:
                cond = child["condition"]
                if is_prose(cond):
                    siblings = [c for j, c in enumerate(children) if j != i]
                    has_working = any(_clause_is_working(s, is_prose) for s in siblings)
                    rows_out.append({
                        "clause_path": child_path,
                        "condition_text": cond,
                        "structural_class": _classify_structural(group_type, has_working),
                    })
            _walk_group(child, child_path, is_prose, rows_out)


def audit_algorithms(
    algo_root: Path = ALGO_ROOT, registry: Optional[dict[str, set[str]]] = None
) -> list[dict]:
    from knowledge_base.engine.redflag_eval import _looks_like_prose_condition

    if registry is None:
        registry = build_candidate_registry()

    rows: list[dict] = []
    for path in sorted(algo_root.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for step in doc.get("decision_tree", []) or []:
            step_rows: list[dict] = []
            _walk_group(
                step.get("evaluate") or {}, "", _looks_like_prose_condition, step_rows
            )
            for row in step_rows:
                confidence, matches = classify_confidence(row["condition_text"], registry)
                rows.append({
                    "file": path.name,
                    "step": step.get("step"),
                    "clause_path": row["clause_path"],
                    "condition_text": row["condition_text"],
                    "structural_class": row["structural_class"],
                    "confidence": confidence,
                    "proposed_clause": (
                        propose_clause(row["condition_text"], matches)
                        if confidence == "HIGH_CONFIDENCE_RENAME"
                        else ""
                    ),
                    "candidate_finding_keys": "; ".join(matches),
                })
    return rows


def write_csv(rows: list[dict], output: Path = DEFAULT_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file", "step", "clause_path", "condition_text", "structural_class",
        "confidence", "proposed_clause", "candidate_finding_keys",
    ]
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--algo-root", type=Path, default=ALGO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = audit_algorithms(args.algo_root)
    write_csv(rows, args.output)

    by_structural: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for row in rows:
        by_structural[row["structural_class"]] = by_structural.get(row["structural_class"], 0) + 1
        by_confidence[row["confidence"]] = by_confidence.get(row["confidence"], 0) + 1

    print(f"Wrote {len(rows)} rows to {args.output}")
    print("By structural class:", by_structural)
    print("By confidence:", by_confidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
