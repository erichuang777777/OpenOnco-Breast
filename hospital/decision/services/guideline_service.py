"""Guideline flowchart builder — turns an Algorithm `decision_tree` (YAML)
into a render-friendly node/edge graph for the frontend visualization.

This is a *presentation* concern, not a clinical one. The engine
(`knowledge_base.engine.algorithm_eval.walk_algorithm`) remains the sole
decision-maker (CHARTER §8.3). This module never selects anything; it only
reshapes the already-authored decision tree so a clinician can *see* the
branching logic and, optionally, the path a given patient took (the engine
trace).

Label resolution relies on the deterministic KB file-naming convention
(`IND-BREAST-TNBC` → `ind_breast_tnbc.yaml`) with a recursive-glob fallback.
Results are cached per (kb_root, kind, id) so an interactive endpoint stays
cheap without loading the whole knowledge base.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Optional

import yaml

# entity "kind" → content sub-directory
_KB_DIR_FOR = {
    "algorithm": "algorithms",
    "indication": "indications",
    "redflag": "redflags",
    "regimen": "regimens",
}


def _entity_filename(entity_id: str) -> str:
    """`IND-BREAST-TNBC` → `ind_breast_tnbc.yaml` (KB naming convention)."""
    return entity_id.strip().lower().replace("-", "_") + ".yaml"


@functools.lru_cache(maxsize=4096)
def _load_entity(kb_root_str: str, kind: str, entity_id: str) -> Optional[dict]:
    """Load a single KB entity YAML by id. Returns None if not found.

    Tries the deterministic filename first, then a recursive glob (handles
    nested folders such as `redflags/universal/`). Cached by argument tuple.
    """
    sub = _KB_DIR_FOR.get(kind)
    if not sub:
        return None
    base = Path(kb_root_str) / sub
    candidate = base / _entity_filename(entity_id)
    path: Optional[Path] = candidate if candidate.is_file() else None
    if path is None:
        matches = list(base.rglob(_entity_filename(entity_id)))
        path = matches[0] if matches else None
    if path is None:
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError):
        return None


def humanize_id(entity_id: str) -> str:
    """`RF-BREAST-HER2-AMP-ACTIONABLE` → `Breast Her2 Amp Actionable`.

    Strips the leading type prefix and title-cases the remainder so a
    clinician sees something readable even when the entity YAML is absent.
    """
    parts = entity_id.split("-")
    if len(parts) > 1 and parts[0].upper() in {"RF", "IND", "ALGO", "REG", "BIO", "DIS"}:
        parts = parts[1:]
    return " ".join(p.capitalize() for p in parts) or entity_id


def _red_flag_label(kb_root_str: str, rf_id: str) -> str:
    rf = _load_entity(kb_root_str, "redflag", rf_id)
    if rf:
        name = rf.get("name") or rf.get("title") or rf.get("definition")
        if isinstance(name, str) and name.strip():
            # definitions can be long; keep the first sentence/clause
            short = name.strip().split(". ")[0]
            return short[:120]
    return humanize_id(rf_id)


def _clause_to_text(clause: Any, kb_root_str: str) -> str:
    """Render one evaluate clause as a short human-readable condition."""
    if not isinstance(clause, dict):
        return str(clause)

    if "red_flag" in clause:
        return f"⚑ {_red_flag_label(kb_root_str, clause['red_flag'])}"
    if "red_flags_any_of" in clause:
        inner = " OR ".join(_red_flag_label(kb_root_str, r) for r in clause["red_flags_any_of"])
        return f"any of: {inner}"
    if "red_flags_all_of" in clause:
        inner = " AND ".join(_red_flag_label(kb_root_str, r) for r in clause["red_flags_all_of"])
        return f"all of: {inner}"
    if "any_of" in clause:
        return " OR ".join(_clause_to_text(c, kb_root_str) for c in clause["any_of"])
    if "all_of" in clause:
        return " AND ".join(_clause_to_text(c, kb_root_str) for c in clause["all_of"])
    if "none_of" in clause:
        return "NOT (" + " OR ".join(_clause_to_text(c, kb_root_str) for c in clause["none_of"]) + ")"
    if "finding" in clause:
        key = clause["finding"]
        if "value" in clause:
            return f"{key} = {clause['value']}"
        if "threshold" in clause and "comparator" in clause:
            return f"{key} {clause['comparator']} {clause['threshold']}"
        return str(key)
    if "condition" in clause:
        return str(clause["condition"]).strip()
    return str(clause)


def _collect_red_flags(evaluate: Any, acc: list[str]) -> None:
    if not isinstance(evaluate, dict):
        return
    for key in ("red_flags_any_of", "red_flags_all_of"):
        for rf in evaluate.get(key, []) or []:
            if rf not in acc:
                acc.append(rf)
    if "red_flag" in evaluate and evaluate["red_flag"] not in acc:
        acc.append(evaluate["red_flag"])
    for key in ("any_of", "all_of", "none_of"):
        for c in evaluate.get(key, []) or []:
            _collect_red_flags(c, acc)


def _evaluate_match(evaluate: Any) -> str:
    """How the listed conditions combine: 'all', 'any', or 'single'."""
    if not isinstance(evaluate, dict):
        return "single"
    if "all_of" in evaluate or "red_flags_all_of" in evaluate:
        return "all"
    if "any_of" in evaluate or "red_flags_any_of" in evaluate:
        return "any"
    return "single"


def _summarize_evaluate(evaluate: Any, kb_root_str: str) -> tuple[list[str], list[str]]:
    """Return (readable condition lines, referenced red-flag ids)."""
    conditions: list[str] = []
    red_flags: list[str] = []
    if not isinstance(evaluate, dict):
        return conditions, red_flags
    _collect_red_flags(evaluate, red_flags)

    # Top-level grouping determines OR vs AND between listed clauses.
    if "any_of" in evaluate:
        conditions = [_clause_to_text(c, kb_root_str) for c in evaluate["any_of"]]
    elif "all_of" in evaluate:
        conditions = [_clause_to_text(c, kb_root_str) for c in evaluate["all_of"]]
    elif "red_flags_any_of" in evaluate:
        conditions = [_red_flag_label(kb_root_str, r) for r in evaluate["red_flags_any_of"]]
    elif "red_flags_all_of" in evaluate:
        conditions = [_red_flag_label(kb_root_str, r) for r in evaluate["red_flags_all_of"]]
    else:
        text = _clause_to_text(evaluate, kb_root_str)
        if text:
            conditions = [text]
    # de-dup while preserving order
    seen: set[str] = set()
    conditions = [c for c in conditions if c and not (c in seen or seen.add(c))]
    return conditions, red_flags


def _indication_node_id(ind_id: str) -> str:
    return f"ind:{ind_id}"


def _indication_details(kb_root_str: str, ind_id: str) -> dict:
    """Best-effort friendly metadata for a terminal indication node."""
    ind = _load_entity(kb_root_str, "indication", ind_id)
    out: dict = {
        "indication_id": ind_id,
        "label": humanize_id(ind_id),
        "regimen_name": None,
        "nccn_category": None,
        "evidence_level": None,
    }
    if not ind:
        return out
    out["nccn_category"] = ind.get("nccn_category")
    out["evidence_level"] = ind.get("evidence_level")
    reg_id = ind.get("recommended_regimen")
    if isinstance(reg_id, str):
        reg = _load_entity(kb_root_str, "regimen", reg_id)
        if reg and isinstance(reg.get("name"), str):
            out["regimen_name"] = reg["name"]
        else:
            out["regimen_name"] = humanize_id(reg_id)
    return out


def build_guideline_graph(algorithm_id: str, *, kb_root: Path | str) -> Optional[dict]:
    """Build a node/edge graph for one algorithm. None if not found."""
    kb_root_str = str(kb_root)
    algo = _load_entity(kb_root_str, "algorithm", algorithm_id)
    if not algo:
        return None

    nodes: list[dict] = []
    edges: list[dict] = []
    ind_nodes_added: set[str] = set()

    def ensure_indication_node(ind_id: str) -> str:
        nid = _indication_node_id(ind_id)
        if nid not in ind_nodes_added:
            details = _indication_details(kb_root_str, ind_id)
            nodes.append({
                "id": nid,
                "kind": "indication",
                "label": details["label"],
                "indication_id": ind_id,
                "regimen_name": details["regimen_name"],
                "nccn_category": details["nccn_category"],
                "evidence_level": details["evidence_level"],
                "conditions": [],
                "red_flags": [],
                "step": None,
                "notes": None,
                "on_path": False,
            })
            ind_nodes_added.add(nid)
        return nid

    decision_tree = algo.get("decision_tree") or []
    step_ids = [s.get("step") for s in decision_tree]

    # Start node
    nodes.append({
        "id": "start",
        "kind": "start",
        "label": "Patient profile",
        "conditions": [],
        "red_flags": [],
        "step": None,
        "notes": None,
        "indication_id": None,
        "regimen_name": None,
        "nccn_category": None,
        "evidence_level": None,
        "on_path": False,
    })
    if step_ids:
        edges.append({
            "source": "start",
            "target": f"step:{step_ids[0]}",
            "branch": None,
            "label": None,
            "on_path": False,
        })

    def branch_target(branch: Any) -> Optional[str]:
        if not isinstance(branch, dict):
            return None
        if "result" in branch:
            res = branch["result"]
            if res is False or res is None:
                return None  # explicit "no indication" leaf
            return ensure_indication_node(res)
        if "next_step" in branch:
            return f"step:{branch['next_step']}"
        return None

    for step in decision_tree:
        sid = step.get("step")
        node_id = f"step:{sid}"
        evaluate = step.get("evaluate") or {}
        conditions, red_flags = _summarize_evaluate(evaluate, kb_root_str)
        nodes.append({
            "id": node_id,
            "kind": "decision",
            "label": f"Step {sid}",
            "step": sid,
            "match": _evaluate_match(evaluate),
            "conditions": conditions,
            "red_flags": red_flags,
            "notes": (step.get("notes") or "").strip() or None,
            "indication_id": None,
            "regimen_name": None,
            "nccn_category": None,
            "evidence_level": None,
            "on_path": False,
        })
        for branch_key, label, branch_name in (
            ("if_true", "Yes", "true"),
            ("if_false", "No", "false"),
        ):
            branch = step.get(branch_key)
            target = branch_target(branch)
            if target is None and isinstance(branch, dict) and branch.get("result") in (False, None):
                # "no indication" leaf — surface as an explicit terminal
                leaf_id = f"{node_id}:{branch_name}:none"
                nodes.append({
                    "id": leaf_id,
                    "kind": "no_indication",
                    "label": "No specific indication",
                    "step": None,
                    "conditions": [],
                    "red_flags": [],
                    "notes": (branch.get("notes") or "").strip() or None if isinstance(branch, dict) else None,
                    "indication_id": None,
                    "regimen_name": None,
                    "nccn_category": None,
                    "evidence_level": None,
                    "on_path": False,
                })
                target = leaf_id
            if target is not None:
                edges.append({
                    "source": node_id,
                    "target": target,
                    "branch": branch_name,
                    "label": label,
                    "on_path": False,
                })

    # Default-fall-through terminal (engine returns default_indication if the
    # tree never resolves a result).
    default_ind = algo.get("default_indication")
    if isinstance(default_ind, str):
        ensure_indication_node(default_ind)

    return {
        "algorithm_id": algo.get("id", algorithm_id),
        "disease_id": algo.get("applicable_to_disease"),
        "line_of_therapy": algo.get("applicable_to_line_of_therapy"),
        "purpose": (algo.get("purpose") or "").strip() or None,
        "default_indication": default_ind,
        "alternative_indication": algo.get("alternative_indication"),
        "sources": list(algo.get("sources") or []),
        "nodes": nodes,
        "edges": edges,
        "has_trace": False,
    }


def overlay_trace(graph: dict, trace: list[dict]) -> dict:
    """Mark nodes/edges that lie on the path the engine actually walked.

    `trace` is `PlanResult.trace`: a list of per-step records
    `{step, outcome, branch, ...}` plus a terminal `{step: None, result}`.
    Mutates and returns `graph`.
    """
    if not trace:
        return graph
    node_by_id = {n["id"]: n for n in graph["nodes"]}
    path_node_ids: set[str] = {"start"}
    # (source, target) pairs that are on the path
    path_edges: set[tuple[str, str]] = set()

    prev_node = "start"
    for entry in trace:
        sid = entry.get("step")
        if sid is not None:
            node_id = f"step:{sid}"
            path_node_ids.add(node_id)
            path_edges.add((prev_node, node_id))
            prev_node = node_id
            branch = entry.get("branch")
            if isinstance(branch, dict) and "result" in branch:
                res = branch["result"]
                if isinstance(res, str):
                    target = _indication_node_id(res)
                    path_node_ids.add(target)
                    path_edges.add((node_id, target))
        else:
            # terminal fall-through entry with a `result`
            res = entry.get("result")
            if isinstance(res, str):
                target = _indication_node_id(res)
                path_node_ids.add(target)
                path_edges.add((prev_node, target))

    for n in graph["nodes"]:
        n["on_path"] = n["id"] in path_node_ids
    for e in graph["edges"]:
        e["on_path"] = (e["source"], e["target"]) in path_edges
    graph["has_trace"] = True
    return graph


def list_algorithms_for_disease(disease_id: Optional[str], *, kb_root: Path | str) -> list[dict]:
    """List algorithm summaries, optionally filtered to one disease."""
    base = Path(kb_root) / "algorithms"
    out: list[dict] = []
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        algo_disease = data.get("applicable_to_disease")
        if disease_id and algo_disease != disease_id:
            continue
        out.append({
            "algorithm_id": data.get("id", path.stem.upper()),
            "disease_id": algo_disease,
            "line_of_therapy": data.get("applicable_to_line_of_therapy"),
            "purpose": (data.get("purpose") or "").strip() or None,
        })
    return out
