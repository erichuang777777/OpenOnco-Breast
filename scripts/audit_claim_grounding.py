"""KB claim-anchor grounding audit (slice 3 of citation-verifier).

Implements Q4 + Q5 of `docs/plans/kb_data_quality_plan_2026-04-29.md`:

  Q4. Add claim-level source anchors where `expected_outcomes` or
      line-of-therapy text is currently detached from a specific
      trial/guideline source.
  Q5. Regression prevention — track citation density / outcome coverage
      / signoff readiness over time.

Two-layer audit:

  1. Detection (no API): walks claim-bearing text fields on Indication,
     Regimen, BiomarkerActionability. For each, records whether the
     entity carries ≥1 cited SRC-* that resolves to a Source entity.

  2. Verification (--semantic, opt-in, requires ANTHROPIC_API_KEY):
     for fields WITH at least one anchor, asks Claude whether the
     cited sources plausibly support the claim. Reuses the
     `check_semantic` function from
     `scripts.tasktorrent.verify_citations` — single source of truth
     for the API integration prevents drift between contributor-side
     and hosted-side verifiers.

Outputs (overwritten each run):

  docs/kb-claim-grounding-report.md     human-readable summary
  docs/kb-claim-grounding-report.json   structured

Cache (skip-on-rerun, opt-out via --no-cache):

  .cache/citation-grounding/<entity_id>__<field>__<hash8>.json

  Each file: {"cached_at": ISO8601, "result": CheckResult-as-dict, ...}
  TTL: 30 days from `cached_at`. Hash is sha256 of (text + sorted
  cited_sources) so any content change invalidates.

Exit codes:
  0 — success (this is an audit, not a gate)
  1 — fatal error (file IO, KB load failure)
  2 — usage error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
KB_CONTENT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
CACHE_DIR = REPO_ROOT / ".cache" / "citation-grounding"
REPORT_MD = REPO_ROOT / "docs" / "kb-claim-grounding-report.md"
REPORT_JSON = REPO_ROOT / "docs" / "kb-claim-grounding-report.json"

CACHE_TTL = timedelta(days=30)


# ---------- Data ----------

@dataclass
class GroundingResult:
    """Outcome of a semantic grounding check on one claim.

    Mirrors `verify_citations.CheckResult` plus claim identity so the
    record is self-describing in the cache and report.
    """

    entity_type: str
    entity_id: str
    field: str
    grounded: Optional[bool] = None  # None when not run / skipped
    confidence: Optional[float] = None
    reasoning: str = ""
    raw_detail: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class AuditMetrics:
    total_claims: int = 0
    claims_with_anchor: int = 0
    by_entity_type: dict = field(default_factory=lambda: defaultdict(
        lambda: {"total": 0, "anchored": 0}
    ))
    semantic_ran: int = 0
    semantic_grounded: int = 0
    semantic_ungrounded: int = 0
    semantic_skipped: int = 0


# ---------- Cache ----------

def _claim_hash(text: str, cited_sources: list[str]) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    for s in sorted(cited_sources):
        h.update(s.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _cache_path(entity_id: str, field_name: str, content_hash: str) -> Path:
    safe_id = entity_id.replace("/", "_").replace(":", "_")
    safe_field = field_name.replace("/", "_")
    return CACHE_DIR / f"{safe_id}__{safe_field}__{content_hash[:16]}.json"


def _read_cache(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    cached_at = payload.get("cached_at")
    if not isinstance(cached_at, str):
        return None
    try:
        ts = datetime.fromisoformat(cached_at)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - ts > CACHE_TTL:
        return None
    return payload


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------- Core audit ----------

def run_audit(
    kb_root: Path,
    *,
    enable_semantic: bool = False,
    limit: Optional[int] = None,
    use_cache: bool = True,
    semantic_fn: Optional[Callable] = None,
    source_titles: Optional[dict[str, str]] = None,
) -> tuple[AuditMetrics, list, list]:
    """Walk the KB, extract claims, optionally run grounding checks.

    Parameters
    ----------
    kb_root
        Path to ``knowledge_base/hosted/content``.
    enable_semantic
        When True, call ``semantic_fn`` for each anchored claim.
    limit
        Cap on entities (NOT claims) processed. None = no cap.
    use_cache
        When True, read/write per-claim cache files in ``CACHE_DIR``.
    semantic_fn
        Override for the API-call function (test injection point).
        Default: ``scripts.tasktorrent.verify_citations.check_semantic``.
    source_titles
        Override for the SRC-id -> "title + notes" map (test injection).

    Returns
    -------
    (metrics, extracted_claims, grounding_results)
    """
    from knowledge_base.validation.loader import clear_load_cache, load_content
    from knowledge_base.engine._claim_extraction import (
        extract_claims,
    )

    clear_load_cache()  # always start with a fresh load
    load_result = load_content(kb_root)
    claims = extract_claims(load_result.entities_by_id)

    # Apply --limit at entity granularity (not claim) so a single
    # entity's multiple claims are kept together.
    if limit is not None and limit > 0:
        kept_entities: set[str] = set()
        capped: list = []
        for c in claims:
            if c.entity_id in kept_entities or len(kept_entities) < limit:
                kept_entities.add(c.entity_id)
                capped.append(c)
        claims = capped

    metrics = AuditMetrics()
    grounding_results: list[GroundingResult] = []

    # Semantic dependencies — load lazily so detection-only mode never
    # imports anthropic.
    semantic_call = None
    Claim = None
    if enable_semantic:
        from scripts.tasktorrent.verify_citations import (
            Claim,
            check_semantic,
            load_master_source_titles,
        )
        semantic_call = semantic_fn if semantic_fn is not None else check_semantic
        if source_titles is None:
            source_titles = load_master_source_titles()

    for c in claims:
        metrics.total_claims += 1
        bucket = metrics.by_entity_type[c.entity_type]
        bucket["total"] += 1
        if c.has_anchor:
            metrics.claims_with_anchor += 1
            bucket["anchored"] += 1

        if not enable_semantic:
            continue
        if not c.has_anchor:
            continue

        content_hash = _claim_hash(c.text, c.cited_sources)
        cache_path = _cache_path(c.entity_id, c.field, content_hash)
        cached = _read_cache(cache_path) if use_cache else None
        if cached is not None:
            metrics.semantic_ran += 1
            res = _grounding_from_cache_payload(c, cached)
        else:
            assert Claim is not None and semantic_call is not None
            api_claim = Claim(
                sidecar=c.entity_path,
                target_id=c.entity_id,
                summary=c.text,
                cited_sources=list(c.cited_sources),
                civic_eids=[],
            )
            check_result = semantic_call(api_claim, source_titles or {})
            res = _grounding_from_check_result(c, check_result)
            metrics.semantic_ran += 1
            if use_cache:
                _write_cache(cache_path, {
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "entity_type": c.entity_type,
                    "entity_id": c.entity_id,
                    "field": c.field,
                    "content_hash": content_hash,
                    "result": asdict(res),
                })

        if res.skipped:
            metrics.semantic_skipped += 1
        elif res.grounded is False:
            metrics.semantic_ungrounded += 1
        elif res.grounded is True:
            metrics.semantic_grounded += 1
        grounding_results.append(res)

    return metrics, claims, grounding_results


def _grounding_from_check_result(claim, check_result) -> GroundingResult:
    """Translate a verify_citations.CheckResult into a GroundingResult."""
    detail = getattr(check_result, "detail", "") or ""
    skipped = (
        ("skipped" in detail.lower())
        or ("n/a" in detail.lower())
        or ("non-blocking" in detail.lower())
    )
    grounded: Optional[bool] = None
    confidence: Optional[float] = None
    reasoning = ""
    if not skipped and detail.startswith("grounded="):
        # Parse "grounded=True conf=0.92 — reasoning text..."
        try:
            head, _, tail = detail.partition(" — ")
            tokens = head.split()
            for tok in tokens:
                if tok.startswith("grounded="):
                    grounded = tok.split("=", 1)[1].lower() == "true"
                elif tok.startswith("conf="):
                    confidence = float(tok.split("=", 1)[1])
            reasoning = tail.strip()
        except (ValueError, IndexError):
            pass
    return GroundingResult(
        entity_type=claim.entity_type,
        entity_id=claim.entity_id,
        field=claim.field,
        grounded=grounded,
        confidence=confidence,
        reasoning=reasoning,
        raw_detail=detail,
        skipped=skipped,
        skip_reason=detail if skipped else "",
    )


def _grounding_from_cache_payload(claim, payload: dict) -> GroundingResult:
    raw = payload.get("result") or {}
    return GroundingResult(
        entity_type=claim.entity_type,
        entity_id=claim.entity_id,
        field=claim.field,
        grounded=raw.get("grounded"),
        confidence=raw.get("confidence"),
        reasoning=raw.get("reasoning") or "",
        raw_detail=raw.get("raw_detail") or "",
        skipped=bool(raw.get("skipped")),
        skip_reason=raw.get("skip_reason") or "",
    )


# ---------- Report writers ----------

def _excerpt(text: str, n: int = 140) -> str:
    """Single-line excerpt for table cells."""
    one_line = " ".join(text.split())
    if len(one_line) > n:
        return one_line[: n - 1] + "…"
    return one_line


def _percent(num: int, denom: int) -> str:
    return f"{(100.0 * num / denom):.1f}%" if denom > 0 else "n/a"


def write_reports(
    metrics: AuditMetrics,
    claims: list,
    grounding_results: list,
    *,
    semantic_enabled: bool,
    md_path: Path = REPORT_MD,
    json_path: Path = REPORT_JSON,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)

    # Top-50 detached claims (claims whose entity has no resolving anchor)
    detached = [c for c in claims if not c.has_anchor]
    # Stable sort: by entity_type then entity_id
    detached.sort(key=lambda c: (c.entity_type, c.entity_id, c.field))
    top_detached = detached[:50]

    ungrounded = [
        g for g in grounding_results
        if g.grounded is False and not g.skipped
    ]

    # ----- Markdown -----
    lines: list[str] = []
    lines.append("# KB Claim-Anchor Grounding Report")
    lines.append("")
    lines.append(f"_Generated_: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append(
        "Audit of claim-bearing prose fields on Indication, Regimen, and "
        "BiomarkerActionability entities. Layer 1 (detection) checks whether "
        "the parent entity cites ≥1 SRC-* anchor; Layer 2 (semantic, opt-in) "
        "asks the Claude API whether each cited source plausibly supports "
        "the claim. Tracks Q4/Q5 of "
        "`docs/plans/kb_data_quality_plan_2026-04-29.md`; v1.0 target ≥90% "
        "anchor coverage."
    )
    lines.append("")
    lines.append("## Top-level metrics")
    lines.append("")
    lines.append("| Metric | Numerator | Denominator | Score |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| Claim-bearing fields with ≥1 anchor | "
        f"{metrics.claims_with_anchor} | {metrics.total_claims} | "
        f"{_percent(metrics.claims_with_anchor, metrics.total_claims)} |"
    )
    if semantic_enabled:
        denom = metrics.semantic_grounded + metrics.semantic_ungrounded
        lines.append(
            f"| Anchored claims with semantic grounding | "
            f"{metrics.semantic_grounded} | {denom} | "
            f"{_percent(metrics.semantic_grounded, denom)} |"
        )
        lines.append(
            f"| Semantic checks skipped (insufficient text/no key) | "
            f"{metrics.semantic_skipped} | {metrics.semantic_ran} | "
            f"{_percent(metrics.semantic_skipped, metrics.semantic_ran)} |"
        )
    lines.append("")
    lines.append("## Per-entity-type breakdown")
    lines.append("")
    lines.append("| Entity type | Total claims | Anchored | Coverage |")
    lines.append("|---|---:|---:|---:|")
    for etype in sorted(metrics.by_entity_type.keys()):
        b = metrics.by_entity_type[etype]
        lines.append(
            f"| {etype} | {b['total']} | {b['anchored']} | "
            f"{_percent(b['anchored'], b['total'])} |"
        )
    lines.append("")
    lines.append(f"## Detached claims (top 50 of {len(detached)})")
    lines.append("")
    if not detached:
        lines.append("_None — every claim-bearing field has at least one cited Source._")
    else:
        lines.append("These entities make claim-bearing assertions but cite no "
                     "resolving SRC-* anchor anywhere on the entity. Each is a "
                     "candidate for a Q4 remediation chunk.")
        lines.append("")
        lines.append("| Entity | Field | Excerpt | Suggested action |")
        lines.append("|---|---|---|---|")
        for c in top_detached:
            lines.append(
                f"| `{c.entity_id}` ({c.entity_type}) | `{c.field}` | "
                f"{_excerpt(c.text)} | "
                f"add SRC-* anchor or downgrade to maintainer-review note |"
            )
    lines.append("")
    if semantic_enabled:
        lines.append(f"## Grounding-fail claims (semantic mode) — {len(ungrounded)}")
        lines.append("")
        if not ungrounded:
            lines.append("_None — all sampled anchors plausibly support their claims._")
        else:
            lines.append("| Entity | Field | Confidence | Reasoning |")
            lines.append("|---|---|---:|---|")
            for g in ungrounded[:50]:
                conf = (
                    f"{g.confidence:.2f}"
                    if isinstance(g.confidence, float) else "n/a"
                )
                lines.append(
                    f"| `{g.entity_id}` ({g.entity_type}) | `{g.field}` | "
                    f"{conf} | {_excerpt(g.reasoning, 200)} |"
                )
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # ----- JSON -----
    json_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "semantic_enabled": semantic_enabled,
        "metrics": {
            "total_claims": metrics.total_claims,
            "claims_with_anchor": metrics.claims_with_anchor,
            "anchor_coverage": (
                metrics.claims_with_anchor / metrics.total_claims
                if metrics.total_claims else None
            ),
            "by_entity_type": {
                k: dict(v) for k, v in metrics.by_entity_type.items()
            },
            "semantic": {
                "ran": metrics.semantic_ran,
                "grounded": metrics.semantic_grounded,
                "ungrounded": metrics.semantic_ungrounded,
                "skipped": metrics.semantic_skipped,
            },
        },
        "detached_top": [
            {
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "field": c.field,
                "excerpt": _excerpt(c.text),
                "entity_path": c.entity_path,
            }
            for c in top_detached
        ],
        "ungrounded": [
            asdict(g) for g in ungrounded[:200]
        ] if semantic_enabled else [],
    }
    json_path.write_text(
        json.dumps(json_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------- CLI ----------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.audit_claim_grounding",
        description=(
            "Audit KB claim-bearing prose for source anchors. Default: "
            "detection-only (no API). --semantic adds Claude grounding check."
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap entities checked (smoke runs)",
    )
    parser.add_argument(
        "--semantic", action="store_true",
        help="Enable Claude API grounding (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache; force re-query for every claim in --semantic mode",
    )
    parser.add_argument(
        "--kb-root", type=Path, default=KB_CONTENT,
        help="Override KB content root (default: knowledge_base/hosted/content)",
    )
    parser.add_argument(
        "--out-md", type=Path, default=REPORT_MD,
        help=f"Markdown report path (default: {REPORT_MD})",
    )
    parser.add_argument(
        "--out-json", type=Path, default=REPORT_JSON,
        help=f"JSON report path (default: {REPORT_JSON})",
    )
    args = parser.parse_args(argv)

    if args.semantic and not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "WARNING: --semantic without ANTHROPIC_API_KEY — grounding "
            "checks will be skipped (non-blocking).",
            file=sys.stderr,
        )

    if not args.kb_root.is_dir():
        print(f"ERROR: KB root not a directory: {args.kb_root}", file=sys.stderr)
        return 1

    try:
        metrics, claims, grounding = run_audit(
            args.kb_root,
            enable_semantic=args.semantic,
            limit=args.limit,
            use_cache=not args.no_cache,
        )
    except Exception as e:  # pragma: no cover (defensive)
        print(f"ERROR: audit failed: {e}", file=sys.stderr)
        return 1

    try:
        write_reports(
            metrics, claims, grounding,
            semantic_enabled=args.semantic,
            md_path=args.out_md,
            json_path=args.out_json,
        )
    except OSError as e:
        print(f"ERROR: writing report failed: {e}", file=sys.stderr)
        return 1

    # Console summary
    print(f"Total claim-bearing fields: {metrics.total_claims}")
    print(
        f"Anchor coverage: {metrics.claims_with_anchor}/{metrics.total_claims} "
        f"({_percent(metrics.claims_with_anchor, metrics.total_claims)})"
    )
    for etype in sorted(metrics.by_entity_type.keys()):
        b = metrics.by_entity_type[etype]
        print(
            f"  {etype}: {b['anchored']}/{b['total']} "
            f"({_percent(b['anchored'], b['total'])})"
        )
    if args.semantic:
        denom = metrics.semantic_grounded + metrics.semantic_ungrounded
        print(
            f"Semantic: {metrics.semantic_grounded}/{denom} grounded, "
            f"{metrics.semantic_ungrounded} ungrounded, "
            f"{metrics.semantic_skipped} skipped"
        )
    print(f"Reports written: {args.out_md} + {args.out_json}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
