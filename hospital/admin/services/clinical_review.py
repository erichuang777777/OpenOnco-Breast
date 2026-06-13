"""Clinical sign-off review bundles.

Gives a Clinical Co-Lead the surface to verify a KB entity before sign-off:
the structured claim (YAML), the specific claim-bearing fields, and — for
every cited Source — its resolved evidence. Because referenced sources
(NCCN/ESMO/…) are link-and-paraphrase-only (SOURCE_INGESTION_SPEC §1–2), we
cannot redistribute the original PDF text; instead we surface the Source
entity's own structured, license-safe evidence (citation, study_design,
key_results, primary_endpoint, page/section locator) plus a deep link
(DOI/PMID/URL) to the original for the reviewer to cross-check.

Read-only over the KB. Recording the actual sign-off decision is the API
layer's job (hospital KbReview + audit); writing `reviewer_signoffs` back
into YAML stays a governed git change (CHARTER §6.1).
"""

from __future__ import annotations

import functools
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# entity "type" → (content sub-dir, label field, disease field path)
_TYPE_DIR = {
    "indication": "indications",
    "algorithm": "algorithms",
    "regimen": "regimens",
    "redflag": "redflags",
    "biomarker_actionability": "biomarker_actionability",
    "source": "sources",
}

# Claim-bearing fields surfaced for review, in display order.
_CLAIM_FIELDS = [
    "recommended_regimen", "concurrent_therapy", "followed_by",
    "evidence_level", "strength_of_recommendation", "nccn_category",
    "expected_outcomes", "hard_contraindications",
    "red_flags_triggering_alternative", "required_tests", "desired_tests",
    "do_not_do", "do_not_do_en",
    "default_indication", "alternative_indication", "output_indications",
    "trigger", "clinical_direction", "severity",
    "name", "purpose", "definition", "rationale", "rationale_ua",
]

_SRC_RE = re.compile(r"^SRC-[A-Z0-9-]+$")


def _entity_filename(entity_id: str) -> str:
    return entity_id.strip().lower().replace("-", "_") + ".yaml"


@functools.lru_cache(maxsize=4096)
def _load(kb_root_str: str, etype: str, entity_id: str) -> Optional[dict]:
    sub = _TYPE_DIR.get(etype)
    if not sub:
        return None
    base = Path(kb_root_str) / sub
    cand = base / _entity_filename(entity_id)
    path = cand if cand.is_file() else None
    if path is None:
        matches = list(base.rglob(_entity_filename(entity_id)))
        path = matches[0] if matches else None
    if path is None:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def _signoff_count(entity: dict) -> int:
    so = entity.get("reviewer_signoffs")
    if isinstance(so, list):
        return len(so)
    if isinstance(so, int):
        return so
    return 0


def _label_for(etype: str, entity: dict) -> str:
    for f in ("name", "title", "purpose", "definition"):
        v = entity.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip().split("\n")[0][:120]
    return entity.get("id", "")


def _disease_for(entity: dict) -> Optional[str]:
    if isinstance(entity.get("applicable_to"), dict):
        d = entity["applicable_to"].get("disease_id")
        if d:
            return d
    return entity.get("applicable_to_disease") or entity.get("disease_id")


def _collect_source_ids(node: Any, acc: list[str]) -> None:
    """Recursively gather every SRC-* id referenced anywhere in an entity."""
    if isinstance(node, str):
        if _SRC_RE.match(node) and node not in acc:
            acc.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _collect_source_ids(v, acc)
    elif isinstance(node, list):
        for v in node:
            _collect_source_ids(v, acc)


def _resolve_citation(kb_root_str: str, src_id: str) -> dict:
    """Resolve a Source entity into a license-safe evidence card."""
    src = _load(kb_root_str, "source", src_id)
    if not src:
        return {"source_id": src_id, "found": False, "title": None}
    cite = src.get("citation") if isinstance(src.get("citation"), dict) else {}
    doi = cite.get("doi") or src.get("doi")
    pmid = cite.get("pmid") or src.get("pmid")
    url = src.get("url") or cite.get("url")
    if not url and doi:
        url = f"https://doi.org/{doi}"
    if not url and pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return {
        "source_id": src_id,
        "found": True,
        "title": src.get("title") or cite.get("title"),
        "type": src.get("type") or src.get("source_type"),
        "hosting": src.get("hosting") or src.get("hosting_mode"),
        "license": (src.get("license") or {}).get("name") if isinstance(src.get("license"), dict) else src.get("license"),
        "citation": {
            "authors": cite.get("authors"),
            "journal": cite.get("journal"),
            "year": cite.get("year") or src.get("version"),
            "volume": cite.get("volume"),
            "pages": cite.get("pages"),
            "doi": doi,
            "pmid": pmid,
        },
        "url": url,
        # license-safe structured evidence (paraphrased in the Source entity)
        "study_design": src.get("study_design"),
        "key_results": src.get("key_results"),
        "primary_endpoint": src.get("primary_endpoint"),
        "section": src.get("section"),
    }


def _stringify(value: Any) -> Any:
    """Compact, readable representation of a claim value for the UI."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, default_flow_style=False).strip()


def build_review_bundle(kb_root: Path | str, etype: str, entity_id: str) -> Optional[dict]:
    kb_root_str = str(kb_root)
    entity = _load(kb_root_str, etype, entity_id)
    if entity is None:
        return None

    claims = []
    for f in _CLAIM_FIELDS:
        if f in entity and entity[f] not in (None, [], "", {}):
            claims.append({"field": f, "value": _stringify(entity[f])})

    # Algorithms: summarize the decision tree rather than dump it raw.
    if etype == "algorithm" and isinstance(entity.get("decision_tree"), list):
        claims.insert(0, {
            "field": "decision_tree",
            "value": f"{len(entity['decision_tree'])} decision step(s)",
        })

    src_ids: list[str] = []
    _collect_source_ids(entity, src_ids)
    citations = [_resolve_citation(kb_root_str, sid) for sid in src_ids]

    raw_yaml = yaml.safe_dump(entity, allow_unicode=True, sort_keys=False)

    return {
        "entity_type": etype,
        "entity_id": entity.get("id", entity_id),
        "label": _label_for(etype, entity),
        "disease_id": _disease_for(entity),
        "signoff_count": _signoff_count(entity),
        "draft": bool(entity.get("draft")),
        "claims": claims,
        "citations": citations,
        "citation_count": len(citations),
        "missing_sources": [c["source_id"] for c in citations if not c["found"]],
        "raw_yaml": raw_yaml,
    }


@functools.lru_cache(maxsize=8)
def _list_unsigned_cached(kb_root_str: str, etype: Optional[str], day: str) -> list[dict]:
    types = [etype] if etype else ["indication", "algorithm", "regimen", "redflag", "biomarker_actionability"]
    out: list[dict] = []
    for t in types:
        base = Path(kb_root_str) / _TYPE_DIR[t]
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.yaml")):
            try:
                e = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(e, dict):
                continue
            count = _signoff_count(e)
            if count >= 2:
                continue  # already two-reviewer signed
            out.append({
                "entity_type": t,
                "entity_id": e.get("id", path.stem.upper()),
                "label": _label_for(t, e),
                "disease_id": _disease_for(e),
                "signoff_count": count,
                "draft": bool(e.get("draft")),
            })
    return out


def list_unsigned(kb_root: Path | str, entity_type: Optional[str] = None) -> list[dict]:
    """All review-gated entities not yet two-reviewer signed. Cached per day."""
    day = datetime.now(timezone.utc).date().isoformat()
    return list(_list_unsigned_cached(str(kb_root), entity_type, day))
