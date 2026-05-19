"""CPIC (Clinical Pharmacogenetics Implementation Consortium) source client.

CPIC publishes peer-reviewed pharmacogenetic dosing guidelines: given a
patient's genotype at a pharmacogene (DPYD, TPMT, NUDT15, CYP2D6, …), the
guideline tells the prescriber how to adjust the dose of the affected
drug. In oncology this matters most for fluoropyrimidines (DPYD → 5-FU /
capecitabine — life-threatening toxicity in poor metabolisers), thiopurines
(TPMT / NUDT15 → 6-MP / azathioprine in ALL), and tamoxifen (CYP2D6).

Guidelines are licensed CC BY 4.0; the underlying allele-function /
diplotype-to-phenotype tables are CC0. Full classification:
`docs/reviews/cpic-license-2026-05-18.md`.

Why we want it
--------------
Pharmacogenomic dosing is the missing layer in the current KB: a DPYD
poor-metaboliser patient routed to FOLFOX should see a hard "reduce 5-FU
to 50%" RedFlag, not the standard regimen at full dose. CPIC carries
that mapping in structured form, free of restrictive licensing, with no
auth required.

Scope of this scaffold
----------------------
Scaffold — not populated ingest. Delivers:

* `CpicClient` subclass of `BaseSourceClient` with caching + rate-limiting
  from the base.
* `CpicQuery` with two modes: `get_guideline` by guideline ID, and
  `search_drug` for drug-gene pairs.
* Live calls gated behind `OPENONCO_CPIC_LIVE=1` so CI cannot hit upstream.
* Offline fixtures under `tests/fixtures/cpic_responses/`.

Upstream endpoint
-----------------
CPIC publishes data via:

1. The REST API at `https://api.cpicpgx.org/v1/` (PostgREST-style;
   query params on entity tables). Documented at
   https://github.com/cpicpgx/cpic-data#api.
2. Static JSON / Excel downloads from https://cpicpgx.org/genes-drugs/.

The scaffold codes against (1). URL templates are class attributes so
they can be patched at test time when CPIC revises the API.
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


_CPIC_LIVE_ENV = "OPENONCO_CPIC_LIVE"
_USER_AGENT = "OpenOnco/0.1 (+https://openonco.info)"


@dataclass
class CpicQuery:
    """Either a single-guideline fetch by guideline ID (mode='get_guideline')
    or a drug/gene search across CPIC's catalog (mode='search_drug').

    `drug` and `gene` may both be set on `search_drug` to scope to a
    specific pair (e.g. DPYD + fluorouracil); either alone returns the
    full set of paired guidelines for that drug or gene.
    """

    mode: Literal["get_guideline", "search_drug"] = "search_drug"
    guideline_id: Optional[str] = None
    drug: str = ""
    gene: str = ""
    max_results: int = 20


class CpicClient(BaseSourceClient[CpicQuery, dict]):
    """CPIC client. CC BY 4.0 / CC0 corpus, no auth required.

    Conservative rate limit: 1 req/s with burst=3. CPIC's PostgREST API
    sits on a small free instance; we stay polite.
    """

    source_id = "SRC-CPIC"
    rate_limit = RateLimit(tokens_per_second=1.0, burst=3)
    cache_ttl_seconds = 7 * 24 * 3600  # 7 days — CPIC publishes ~quarterly
    api_version = "v1"

    base_url: str = "https://api.cpicpgx.org/v1"
    guideline_path: str = "/guideline?id=eq.{guideline_id}"
    pair_path: str = "/pair"

    def __init__(self, cache: Optional[CacheBackend] = None) -> None:
        super().__init__(cache=cache)

    # ── Subclass hook ────────────────────────────────────────────────────

    def _fetch_raw(self, query: CpicQuery) -> tuple[dict, Optional[str]]:
        if not self._is_live():
            raise RuntimeError(
                f"CPIC live calls are gated behind env var {_CPIC_LIVE_ENV}=1. "
                "Set it explicitly to fetch from api.cpicpgx.org; tests "
                "should use a stubbed CacheBackend or monkeypatch _fetch_raw."
            )
        if query.mode == "get_guideline":
            return self._fetch_guideline(query), self.api_version
        return self._fetch_pair_search(query), self.api_version

    # ── Public helpers ──────────────────────────────────────────────────

    @staticmethod
    def _is_live() -> bool:
        return os.environ.get(_CPIC_LIVE_ENV) in ("1", "true", "TRUE", "yes")

    def _fetch_guideline(self, query: CpicQuery) -> dict:
        if not query.guideline_id:
            raise ValueError("CpicQuery.mode='get_guideline' requires guideline_id")
        url = self.base_url + self.guideline_path.format(
            guideline_id=urllib.parse.quote(query.guideline_id, safe="")
        )
        return _http_get_json(url)

    def _fetch_pair_search(self, query: CpicQuery) -> dict:
        # PostgREST filter syntax: drugid=eq.<name>, genesymbol=eq.<gene>.
        # `limit` caps server-side; we also pageSize-cap in client to be safe.
        params: list[tuple[str, str]] = []
        if query.drug:
            params.append(("drugid", f"eq.{query.drug}"))
        if query.gene:
            params.append(("genesymbol", f"eq.{query.gene}"))
        params.append(("limit", str(min(query.max_results, 100))))
        url = self.base_url + self.pair_path + "?" + urllib.parse.urlencode(params)
        return _http_get_json(url)

    def health(self) -> dict:
        if not self._is_live():
            return {"ok": True, "latency_ms": None, "last_error": None,
                    "note": f"{_CPIC_LIVE_ENV} not set; offline scaffold only"}
        try:
            self._fetch_pair_search(CpicQuery(mode="search_drug", drug="fluorouracil", max_results=1))
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
    # PostgREST returns arrays at the top level for table queries. Wrap so
    # the downstream contract (dict) is consistent across modes.
    if isinstance(parsed, list):
        return {"results": parsed}
    return parsed


__all__ = ["CpicClient", "CpicQuery"]
