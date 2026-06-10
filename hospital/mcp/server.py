#!/usr/bin/env python3
"""OpenOnco MCP Server — stdio JSON-RPC 2.0 transport.

Exposes the OpenOnco KB and rule engine as MCP tools so that Claude Desktop
(or any MCP-compatible client) can query treatment plans, biomarker data,
and clinical trials without direct REST API access.

Usage (Claude Desktop config):
    {
      "mcpServers": {
        "openonco": {
          "command": "python",
          "args": ["/path/to/OpenOnco-Breast/hospital/mcp/server.py"],
          "env": { "KB_ROOT": "knowledge_base/hosted/content" }
        }
      }
    }

Or via make:
    make mcp
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# ── KB root resolution ─────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import os
_KB_ROOT = Path(os.environ.get("KB_ROOT", str(_REPO_ROOT / "knowledge_base/hosted/content")))

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
_log = logging.getLogger("openonco-mcp")

# ── Lazy-loaded singletons ─────────────────────────────────────────────────────
_kb_cache: dict | None = None
_engine_cache = None


def _kb() -> dict:
    global _kb_cache
    if _kb_cache is None:
        from knowledge_base.validation.loader import load_content
        result = load_content(_KB_ROOT)
        _kb_cache = result.entities_by_id
    return _kb_cache


def _engine():
    global _engine_cache
    if _engine_cache is None:
        from hospital.decision.services.onco_engine_client import engine
        _engine_cache = engine
    return _engine_cache


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "generate_treatment_plan",
        "description": (
            "Generate evidence-based treatment plan for an oncology patient using "
            "OpenOnco's rule engine and knowledge base. Returns standard + alternative "
            "treatment tracks with NCCN/evidence grading and gap analysis."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["disease_id"],
            "properties": {
                "disease_id": {
                    "type": "string",
                    "description": "OpenOnco disease ID, e.g. 'DIS-BREAST'. Use list_diseases to find IDs.",
                },
                "biomarkers": {
                    "type": "object",
                    "description": "Biomarker results, e.g. {\"er\": \"positive\", \"her2\": \"negative\", \"brca1\": \"positive\"}",
                },
                "findings": {
                    "type": "object",
                    "description": "Clinical findings, e.g. {\"stage\": \"IIA\", \"brain_mets\": false, \"ki67\": 25}",
                },
                "demographics": {
                    "type": "object",
                    "description": "Patient demographics: {\"age\": 52, \"sex\": \"female\", \"ecog\": 0}",
                },
                "line_of_therapy": {
                    "type": "integer",
                    "default": 1,
                    "description": "Line of therapy (1 = first-line, 2 = second-line, etc.)",
                },
                "include_gaps": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include decision-gap analysis (missing tests that would change the plan)",
                },
            },
        },
    },
    {
        "name": "list_diseases",
        "description": "List all diseases available in the OpenOnco knowledge base with their IDs and names.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Optional keyword to filter by name (e.g. 'breast', 'lung')",
                },
            },
        },
    },
    {
        "name": "get_disease_info",
        "description": "Get detailed information about a specific disease from the KB including subtypes, staging, and receptor profiles.",
        "inputSchema": {
            "type": "object",
            "required": ["disease_id"],
            "properties": {
                "disease_id": {"type": "string", "description": "Disease ID, e.g. 'DIS-BREAST'"},
            },
        },
    },
    {
        "name": "get_biomarker_info",
        "description": "Get clinical information about a biomarker including testing methods and clinical significance.",
        "inputSchema": {
            "type": "object",
            "required": ["biomarker_id"],
            "properties": {
                "biomarker_id": {"type": "string", "description": "Biomarker ID, e.g. 'BIO-BRCA1'"},
            },
        },
    },
    {
        "name": "search_clinical_trials",
        "description": "Search ClinicalTrials.gov for open trials matching a condition and optional location.",
        "inputSchema": {
            "type": "object",
            "required": ["condition"],
            "properties": {
                "condition": {"type": "string", "description": "Disease or condition, e.g. 'breast cancer'"},
                "location": {"type": "string", "description": "Country or city, e.g. 'Taiwan'"},
                "max_results": {"type": "integer", "default": 5, "description": "Maximum number of results"},
            },
        },
    },
    {
        "name": "get_drug_info",
        "description": "Get drug information from the OpenOnco KB including mechanism, indications, and standard dosing.",
        "inputSchema": {
            "type": "object",
            "required": ["drug_id"],
            "properties": {
                "drug_id": {"type": "string", "description": "Drug ID, e.g. 'DRG-TAMOXIFEN'"},
            },
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────

def _tool_generate_treatment_plan(args: dict) -> str:
    disease_id = args["disease_id"]
    biomarkers = args.get("biomarkers") or {}
    findings = args.get("findings") or {}
    demographics = args.get("demographics") or {}
    line_of_therapy = int(args.get("line_of_therapy") or 1)
    include_gaps = bool(args.get("include_gaps", True))

    patient = {
        "patient_id": "MCP-QUERY",
        "disease": {"id": disease_id},
        "line_of_therapy": line_of_therapy,
        "demographics": demographics,
        "findings": findings,
        "biomarkers": biomarkers,
    }

    eng = _engine()
    result = eng.generate_plan(patient, kb_root=_KB_ROOT)

    if result.plan is None:
        warnings = "\n".join(result.warnings or [])
        return f"No plan generated for disease {disease_id}.\nWarnings:\n{warnings}"

    lines = [
        f"# Treatment Plan — {disease_id}",
        f"Algorithm: {result.algorithm_id}",
        f"Plan ID: {result.plan.id}",
        "",
    ]

    for track in result.plan.tracks:
        label = track.label_en or track.label or track.track_id
        default_marker = " ★ DEFAULT" if track.is_default else ""
        lines.append(f"## {label}{default_marker}")
        lines.append(f"Indication: {track.indication_id}")

        regimen = track.regimen_data or {}
        if isinstance(regimen, dict) and regimen.get("name"):
            lines.append(f"Regimen: {regimen['name']}")
            if regimen.get("drugs"):
                drugs = ", ".join(
                    (d if isinstance(d, str) else d.get("drug_id", "")) for d in regimen["drugs"]
                )
                lines.append(f"Drugs: {drugs}")

        ind = track.indication_data or {}
        if isinstance(ind, dict):
            if ind.get("evidence_level"):
                lines.append(f"Evidence level: {ind['evidence_level']}")
            if ind.get("nccn_category"):
                lines.append(f"NCCN category: {ind['nccn_category']}")
            outcomes = ind.get("expected_outcomes") or {}
            if outcomes.get("median_overall_survival_months"):
                lines.append(f"Median OS: {outcomes['median_overall_survival_months']} months")

        if track.selection_reason:
            lines.append(f"Selection reason: {track.selection_reason}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings[:5]:
            lines.append(f"- {w}")
        lines.append("")

    # Gap analysis
    if include_gaps:
        from hospital.decision.services.plan_service import compute_gaps
        from hospital.decision.schemas.plan import PatientInput, DiseaseInput, DemographicsInput
        try:
            patient_input = PatientInput(
                disease=DiseaseInput(id=disease_id),
                line_of_therapy=line_of_therapy,
                demographics=DemographicsInput(**{k: v for k, v in demographics.items() if k in ("age", "sex", "ecog")}),
                findings=findings,
                biomarkers=biomarkers,
            )
            gaps = compute_gaps(patient_input, result)
            if gaps:
                lines.append("## Decision Gaps (missing tests that would change the plan)")
                for g in gaps:
                    test = f" → order: {g.recommended_test}" if g.recommended_test else ""
                    lines.append(f"- **{g.field}**: {g.rationale}{test}")
                lines.append("")
        except Exception as exc:
            _log.warning("gap analysis failed: %s", exc)

    return "\n".join(lines)


def _tool_list_diseases(args: dict) -> str:
    kb = _kb()
    kw = (args.get("filter") or "").lower()
    lines = ["# Diseases in OpenOnco KB", ""]
    count = 0
    for eid, entity in kb.items():
        if not eid.startswith("DIS-"):
            continue
        data = entity.get("data", {}) if isinstance(entity, dict) else {}
        names = data.get("names", {}) or {}
        en_name = names.get("english") or names.get("preferred") or eid
        if kw and kw not in eid.lower() and kw not in en_name.lower():
            continue
        lines.append(f"- **{eid}**: {en_name}")
        count += 1
    lines.append(f"\nTotal: {count} diseases")
    return "\n".join(lines)


def _tool_get_disease_info(args: dict) -> str:
    kb = _kb()
    disease_id = args["disease_id"]
    entity = kb.get(disease_id)
    if not entity:
        return f"Disease '{disease_id}' not found. Use list_diseases to find valid IDs."

    data = entity.get("data", {}) if isinstance(entity, dict) else {}
    names = data.get("names", {}) or {}
    codes = data.get("codes", {}) or {}

    lines = [
        f"# {disease_id}",
        f"**Name:** {names.get('english') or names.get('preferred', disease_id)}",
        f"**Ukrainian:** {names.get('ukrainian', '')}",
        f"**ICD-10:** {codes.get('icd_10', '')}",
        f"**ICD-O-3:** {codes.get('icd_o_3_morphology', '')}",
        f"**OncotreeCode:** {data.get('oncotree_code', '')}",
        "",
    ]

    subtypes = data.get("receptor_subtypes") or data.get("archetype")
    if subtypes:
        lines.append(f"**Subtypes/Archetype:** {json.dumps(subtypes, ensure_ascii=False)}")

    staging = data.get("stage_strata")
    if staging:
        lines.append(f"**Staging:** {json.dumps(staging, ensure_ascii=False)[:300]}")

    return "\n".join(lines)


def _tool_get_biomarker_info(args: dict) -> str:
    kb = _kb()
    bio_id = args["biomarker_id"]
    entity = kb.get(bio_id)
    if not entity:
        close = [k for k in kb if k.startswith("BIO-") and bio_id.replace("BIO-", "").upper() in k][:5]
        hint = f"\nDid you mean: {', '.join(close)}" if close else ""
        return f"Biomarker '{bio_id}' not found.{hint}"

    data = entity.get("data", {}) if isinstance(entity, dict) else {}
    names = data.get("names", {}) or {}

    lines = [
        f"# {bio_id}",
        f"**Name:** {names.get('english') or names.get('preferred', bio_id)}",
    ]
    for field in ("clinical_significance", "testing_method", "actionability_tier", "notes"):
        val = data.get(field)
        if val:
            lines.append(f"**{field.replace('_', ' ').title()}:** {val}")

    return "\n".join(lines)


def _tool_search_clinical_trials(args: dict) -> str:
    try:
        from knowledge_base.clients.ctgov_client import search_trials
        condition = args["condition"]
        location = args.get("location", "")
        max_results = int(args.get("max_results") or 5)

        results = search_trials(condition=condition, location=location, max_results=max_results)
        if not results:
            return f"No open trials found for '{condition}'" + (f" in {location}" if location else "") + "."

        lines = [f"# Clinical Trials: {condition}", ""]
        for t in results[:max_results]:
            nct = t.get("nct_id") or t.get("id", "")
            title = t.get("title") or t.get("brief_title", "")
            status = t.get("status") or t.get("overall_status", "")
            phase = t.get("phase", "")
            lines.append(f"## {nct} — {title}")
            lines.append(f"Status: {status}  Phase: {phase}")
            sites = t.get("locations") or []
            if sites:
                site_names = ", ".join(
                    (s.get("facility") or s if isinstance(s, str) else "") for s in sites[:3]
                )
                lines.append(f"Sites: {site_names}")
            lines.append(f"Details: https://clinicaltrials.gov/study/{nct}")
            lines.append("")
        return "\n".join(lines)
    except Exception as exc:
        return f"Trial search failed: {exc}"


def _tool_get_drug_info(args: dict) -> str:
    kb = _kb()
    drug_id = args["drug_id"]
    entity = kb.get(drug_id)
    if not entity:
        close = [k for k in kb if k.startswith("DRG-") and drug_id.replace("DRG-", "").upper() in k][:5]
        hint = f"\nDid you mean: {', '.join(close)}" if close else ""
        return f"Drug '{drug_id}' not found.{hint}"

    data = entity.get("data", {}) if isinstance(entity, dict) else {}
    names = data.get("names", {}) or {}

    lines = [
        f"# {drug_id}",
        f"**Name:** {names.get('preferred') or names.get('english', drug_id)}",
    ]
    for field in ("mechanism", "drug_class", "administration_route", "standard_dosing", "notes"):
        val = data.get(field)
        if val:
            lines.append(f"**{field.replace('_', ' ').title()}:** {val}")

    return "\n".join(lines)


TOOL_HANDLERS = {
    "generate_treatment_plan": _tool_generate_treatment_plan,
    "list_diseases":           _tool_list_diseases,
    "get_disease_info":        _tool_get_disease_info,
    "get_biomarker_info":      _tool_get_biomarker_info,
    "search_clinical_trials":  _tool_search_clinical_trials,
    "get_drug_info":           _tool_get_drug_info,
}


# ── JSON-RPC stdio loop ────────────────────────────────────────────────────────

def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _handle(msg: dict) -> dict | None:
    method = msg.get("method", "")
    id_ = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return _ok(id_, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "openonco", "version": "0.1.0"},
        })

    if method == "notifications/initialized":
        return None  # no response for notifications

    if method == "tools/list":
        return _ok(id_, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name") or ""
        arguments = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return _err(id_, -32601, f"Unknown tool: {name}")
        try:
            text = handler(arguments)
            return _ok(id_, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:
            _log.exception("tool %s failed", name)
            return _err(id_, -32603, f"Tool error: {exc}")

    if method == "ping":
        return _ok(id_, {})

    if id_ is not None:
        return _err(id_, -32601, f"Method not found: {method}")
    return None  # unknown notification — ignore


def main() -> None:
    _log.info("OpenOnco MCP server starting (KB: %s)", _KB_ROOT)
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps(_err(None, -32700, f"Parse error: {exc}")) + "\n")
            sys.stdout.flush()
            continue

        response = _handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
