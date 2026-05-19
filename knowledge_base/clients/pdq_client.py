"""NCI PDQ (Physician Data Query) source client.

PDQ is the National Cancer Institute's free, government-authored corpus
of cancer information summaries (treatment, screening, prevention,
supportive care) maintained in two parallel registers: a Health
Professional (HP) version and a Patient version. As a US federal-government
work, PDQ content is **public domain** under 17 U.S.C. §105 and may be
reused without permission — see `docs/reviews/pdq-license-2026-05-18.md`
for the full classification.

Why we want it
--------------
The audit `docs/reviews/openonco-state-audit-2026-05-17.md` flagged that
the "why this regimen" prose fields on Indications are thin. PDQ
treatment summaries are exactly that prose, written by an NCI editorial
board, fully citable, and license-clean for free public reuse.

Scope of this scaffold
----------------------
This is a **scaffold**, not a populated ingest. It delivers:

* The `PdqClient` subclass of `BaseSourceClient` with caching + rate
  limiting from the base.
* A `PdqQuery` dataclass with two modes: `get_summary` by CDR ID,
  and `search` by free-text terms.
* No live calls happen in tests — fixtures live under
  `tests/fixtures/pdq_responses/`.

Live calls are gated behind the `OPENONCO_PDQ_LIVE` env var so this code
cannot accidentally hit the upstream during a CI run.

Upstream endpoint
-----------------
NCI Cancer.gov publishes PDQ summaries via two surfaces:

1. **Syndication API** at `https://www.cancer.gov/syndication` — JSON
   endpoints for content fragments, indexed by CDR (Cancer Data
   Repository) ID. Documented at
   https://www.cancer.gov/syndication/api-documentation.
2. **Cancer.gov pages** at `https://www.cancer.gov/types/<cancer>/hp/<topic>-treatment-pdq`
   — human-readable HTML, the same content as a rendered fallback.

The scaffold codes against (1). The exact URL templates are kept as
class attributes so they can be patched at test time or revised when
NCI updates the API.
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


_PDQ_LIVE_ENV = "OPENONCO_PDQ_LIVE"
_USER_AGENT = "OpenOnco/0.1 (+https://openonco.info)"


@dataclass
class PdqQuery:
    """Either a single-summary fetch by CDR ID (mode='get_summary') or a
    free-text search across the PDQ index (mode='search').

    `audience` selects the HP vs Patient register — they cover the same
    topics but differ in reading level and degree of clinical detail.
    """

    mode: Literal["get_summary", "search"] = "get_summary"
    cdr_id: Optional[str] = None
    terms: str = ""
    audience: Literal["hp", "patient"] = "hp"
    max_results: int = 20


class PdqClient(BaseSourceClient[PdqQuery, dict]):
    """NCI PDQ client. Public-domain corpus, no auth required.

    Conservative rate limit: 1 req/s with burst=3. NCI does not publish a
    formal rate limit for the syndication API; this stays well under any
    plausible threshold and avoids hammering cancer.gov.
    """

    source_id = "SRC-PDQ"
    rate_limit = RateLimit(tokens_per_second=1.0, burst=3)
    cache_ttl_seconds = 7 * 24 * 3600  # 7 days — PDQ content updates ~monthly
    api_version = "syndication-v1"

    # Endpoint templates. Patchable at test time; documented in the module
    # docstring above.
    base_url: str = "https://www.cancer.gov/syndication"
    summary_path: str = "/syndication/json/summary/{cdr_id}"
    search_path: str = "/syndication/json/summaries"

    def __init__(self, cache: Optional[CacheBackend] = None) -> None:
        super().__init__(cache=cache)

    # ── Subclass hook ────────────────────────────────────────────────────

    def _fetch_raw(self, query: PdqQuery) -> tuple[dict, Optional[str]]:
        if not self._is_live():
            raise RuntimeError(
                f"PDQ live calls are gated behind env var {_PDQ_LIVE_ENV}=1. "
                "Set it explicitly to fetch from cancer.gov; tests should "
                "use a stubbed CacheBackend or monkeypatch _fetch_raw."
            )
        if query.mode == "get_summary":
            return self._fetch_summary(query), self.api_version
        return self._fetch_search(query), self.api_version

    # ── Public helpers ──────────────────────────────────────────────────

    @staticmethod
    def _is_live() -> bool:
        return os.environ.get(_PDQ_LIVE_ENV) in ("1", "true", "TRUE", "yes")

    def _fetch_summary(self, query: PdqQuery) -> dict:
        if not query.cdr_id:
            raise ValueError("PdqQuery.mode='get_summary' requires cdr_id")
        url = self.base_url + self.summary_path.format(
            cdr_id=urllib.parse.quote(query.cdr_id, safe="")
        )
        return _http_get_json(url)

    def _fetch_search(self, query: PdqQuery) -> dict:
        params = {
            "audience": query.audience,
            "terms": query.terms,
            "size": str(min(query.max_results, 50)),
        }
        url = self.base_url + self.search_path + "?" + urllib.parse.urlencode(params)
        return _http_get_json(url)

    def health(self) -> dict:
        """Healthcheck: when live, ping the index; when not live, report
        that the gate is closed (still 'ok' — the client is functional,
        it's just not allowed to hit upstream)."""
        if not self._is_live():
            return {"ok": True, "latency_ms": None, "last_error": None,
                    "note": f"{_PDQ_LIVE_ENV} not set; offline scaffold only"}
        try:
            self._fetch_search(PdqQuery(mode="search", terms="cancer", max_results=1))
            return {"ok": True, "latency_ms": None, "last_error": None}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "latency_ms": None, "last_error": str(exc)}


# ── Module-level helpers ───────────────────────────────────────────────────


def _http_get_json(url: str, timeout: int = 20) -> dict:
    """Minimal stdlib GET → JSON. Tests substitute via monkeypatch."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


__all__ = ["PdqClient", "PdqQuery"]
