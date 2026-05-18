"""NCI Thesaurus (NCIt) source client.

NCIt is the National Cancer Institute's reference vocabulary for cancer
concepts — diseases, biomarkers, drugs, anatomic sites, procedures, with
preferred terms, synonyms, definitions, and cross-references to other
vocabularies (ICD-10, MeSH, SNOMED-CT). Each concept carries a stable
NCIt code (e.g. C4878 = Non-Small Cell Lung Carcinoma).

Why we want it
--------------
The state audit (`docs/reviews/openonco-state-audit-2026-05-17.md`) and
the patient-input flow both rely on free-text disease/biomarker terms
resolving cleanly to KB entities. NCIt is the canonical vocabulary
backing that normalization:

- "lung cancer" / "non-small cell lung cancer" / "NSCLC" → NCIt C2926 →
  our `DIS-NSCLC`
- "EGFR positive" / "EGFR mutation" → NCIt C20188 (EGFR Mutation) →
  our `BIO-EGFR-MUTATION`

This scaffold lands the client + Source entity + optional `ncit_code`
fields on `Disease.codes` and `BiomarkerExternalIDs`. Populating the
codes per-entity is a separate clinical-content workstream gated by
CHARTER §6.1.

Licensing
---------
NCIt content is a work of the US federal government (NCI Enterprise
Vocabulary Services, NIH). Public domain under 17 U.S.C. §105. Full
classification: `docs/reviews/ncit-license-2026-05-18.md`.

Upstream endpoint
-----------------
NCI Enterprise Vocabulary Services (EVS) REST API at
`https://api-evsrest.nci.nih.gov/api/v1/`. Endpoints used:

- `GET /concept/ncit/{code}` — concept by stable NCIt code
- `GET /concept/ncit/search?term=…` — free-text concept search

Documentation: https://api-evsrest.nci.nih.gov/swagger-ui.html. Field
shapes and search parameters are stable; the URL templates are class
attributes so a future EVS revision can be patched without touching
the integration code.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Literal, Optional

from knowledge_base.clients.base import (
    BaseSourceClient,
    CacheBackend,
    RateLimit,
)


_NCIT_LIVE_ENV = "OPENONCO_NCIT_LIVE"
_USER_AGENT = "OpenOnco/0.1 (+https://openonco.info)"


@dataclass
class NcitQuery:
    """Either a single-concept fetch by NCIt code (mode='get_concept')
    or a free-text search (mode='search').

    `include` controls EVS field expansion. Default "summary" keeps the
    response small (code, name, definition, synonyms). "full" pulls
    parent/child relationships and external cross-refs.
    """

    mode: Literal["get_concept", "search"] = "get_concept"
    code: Optional[str] = None
    term: str = ""
    include: Literal["minimal", "summary", "full"] = "summary"
    max_results: int = 20


class NcitClient(BaseSourceClient[NcitQuery, dict]):
    """NCIt EVS client. Public-domain corpus, no auth required.

    Conservative rate limit: 1 req/s with burst=3. EVS does not publish
    a formal rate limit; this stays well under any plausible threshold.
    Cache TTL is long (30 days) because NCIt content updates monthly
    and individual concept records change infrequently.
    """

    source_id = "SRC-NCIT"
    rate_limit = RateLimit(tokens_per_second=1.0, burst=3)
    cache_ttl_seconds = 30 * 24 * 3600
    api_version = "v1"

    base_url: str = "https://api-evsrest.nci.nih.gov/api/v1"
    concept_path: str = "/concept/ncit/{code}"
    search_path: str = "/concept/ncit/search"

    def __init__(self, cache: Optional[CacheBackend] = None) -> None:
        super().__init__(cache=cache)

    # ── Subclass hook ────────────────────────────────────────────────────

    def _fetch_raw(self, query: NcitQuery) -> tuple[dict, Optional[str]]:
        if not self._is_live():
            raise RuntimeError(
                f"NCIt live calls are gated behind env var {_NCIT_LIVE_ENV}=1. "
                "Set it explicitly to fetch from api-evsrest.nci.nih.gov; "
                "tests should use a stubbed CacheBackend or monkeypatch "
                "_fetch_raw."
            )
        if query.mode == "get_concept":
            return self._fetch_concept(query), self.api_version
        return self._fetch_search(query), self.api_version

    # ── Public helpers ──────────────────────────────────────────────────

    @staticmethod
    def _is_live() -> bool:
        return os.environ.get(_NCIT_LIVE_ENV) in ("1", "true", "TRUE", "yes")

    def _fetch_concept(self, query: NcitQuery) -> dict:
        if not query.code:
            raise ValueError("NcitQuery.mode='get_concept' requires code")
        path = self.concept_path.format(code=urllib.parse.quote(query.code, safe=""))
        params = {"include": query.include}
        url = self.base_url + path + "?" + urllib.parse.urlencode(params)
        return _http_get_json(url)

    def _fetch_search(self, query: NcitQuery) -> dict:
        params = {
            "term": query.term,
            "include": query.include,
            "pageSize": str(min(query.max_results, 100)),
        }
        url = self.base_url + self.search_path + "?" + urllib.parse.urlencode(params)
        return _http_get_json(url)

    def health(self) -> dict:
        if not self._is_live():
            return {"ok": True, "latency_ms": None, "last_error": None,
                    "note": f"{_NCIT_LIVE_ENV} not set; offline scaffold only"}
        try:
            # C2926 = Non-Small Cell Lung Carcinoma — stable canary code,
            # has existed since NCIt's earliest published versions.
            self._fetch_concept(NcitQuery(mode="get_concept", code="C2926"))
            return {"ok": True, "latency_ms": None, "last_error": None}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "latency_ms": None, "last_error": str(exc)}


# ── Module-level helpers ───────────────────────────────────────────────────


def _http_get_json(url: str, timeout: int = 20) -> dict:
    """Minimal stdlib GET → JSON. Tests substitute via monkeypatch."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    # EVS search endpoint returns {concepts: [...], total: N} — already a
    # dict. Concept endpoint returns the concept dict directly. No
    # wrapping needed (unlike PostgREST in cpic_client).
    return parsed


__all__ = ["NcitClient", "NcitQuery"]
