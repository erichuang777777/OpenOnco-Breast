"""Coverage fixes for `knowledge_base/clients/ctgov_client.py`:

1. Pagination — `search_trials` previously capped `pageSize` at
   `min(max_results, 25)` on a *single* request, so any `max_results`
   above 25 silently returned at most 25 studies. Now paginates via
   ctgov v2's `nextPageToken` until `max_results` is reached or pages
   run out, bounded by `_MAX_PAGES`.
2. Query-field correctness — biomarkers must flow through `query.term`,
   not `query.intr` (drug/device names); `status="open"` must map to
   the RECRUITING|ACTIVE_NOT_RECRUITING|ENROLLING_BY_INVITATION filter
   that matches `engine.experimental_options._OPEN_STATUSES`.
"""

from __future__ import annotations

import urllib.parse

from knowledge_base.clients import ctgov_client
from knowledge_base.clients.ctgov_client import search_trials


def _fake_study(nct: str) -> dict:
    return {"NCTId": nct, "BriefTitle": nct, "OverallStatus": "RECRUITING"}


def test_pagination_collects_more_than_one_page(monkeypatch):
    """max_results=60 with 25-per-page-equivalent pages must make more
    than one request and return studies from every page."""
    calls: list[dict] = []

    def _fake_get(url, timeout=15):
        parsed = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        calls.append(params)
        page = int(params.get("pageToken", "0"))
        studies = [_fake_study(f"NCT{page}{i:03d}") for i in range(30)]
        result = {"studies": studies}
        if page < 1:
            result["nextPageToken"] = "1"
        return result

    monkeypatch.setattr(ctgov_client, "_get", _fake_get)
    results = search_trials("lung cancer", max_results=60)

    assert len(calls) == 2, "must page beyond the first 30-study page"
    assert len(results) == 60
    ids = {r["nct_id"] for r in results}
    assert "NCT0000" in ids
    assert "NCT1000" in ids


def test_pagination_stops_when_no_next_page_token(monkeypatch):
    def _fake_get(url, timeout=15):
        return {"studies": [_fake_study("NCT0000")]}  # no nextPageToken

    monkeypatch.setattr(ctgov_client, "_get", _fake_get)
    results = search_trials("rare cancer", max_results=100)
    assert len(results) == 1


def test_pagination_bounded_by_max_pages(monkeypatch):
    """A pathological server that always returns a nextPageToken must
    not be followed forever."""
    call_count = {"n": 0}

    def _fake_get(url, timeout=15):
        call_count["n"] += 1
        return {"studies": [_fake_study(f"NCT{call_count['n']:04d}")], "nextPageToken": "x"}

    monkeypatch.setattr(ctgov_client, "_get", _fake_get)
    search_trials("common cancer", max_results=10_000)
    assert call_count["n"] <= ctgov_client._MAX_PAGES


def test_term_param_maps_to_query_term(monkeypatch):
    seen = {}

    def _fake_get(url, timeout=15):
        parsed = urllib.parse.urlparse(url)
        seen.update(urllib.parse.parse_qsl(parsed.query))
        return {"studies": []}

    monkeypatch.setattr(ctgov_client, "_get", _fake_get)
    search_trials("NSCLC", term="EGFR mutation")
    assert seen.get("query.term") == "EGFR mutation"
    assert "query.intr" not in seen


def test_intervention_param_still_maps_to_query_intr(monkeypatch):
    """Existing callers passing a real drug name must be unaffected."""
    seen = {}

    def _fake_get(url, timeout=15):
        parsed = urllib.parse.urlparse(url)
        seen.update(urllib.parse.parse_qsl(parsed.query))
        return {"studies": []}

    monkeypatch.setattr(ctgov_client, "_get", _fake_get)
    search_trials("NSCLC", intervention="pembrolizumab")
    assert seen.get("query.intr") == "pembrolizumab"
    assert "query.term" not in seen


def test_open_status_maps_to_multi_value_filter(monkeypatch):
    seen = {}

    def _fake_get(url, timeout=15):
        parsed = urllib.parse.urlparse(url)
        seen.update(urllib.parse.parse_qsl(parsed.query))
        return {"studies": []}

    monkeypatch.setattr(ctgov_client, "_get", _fake_get)
    search_trials("NSCLC", status="open")
    assert seen.get("filter.overallStatus") == (
        "RECRUITING|ACTIVE_NOT_RECRUITING|ENROLLING_BY_INVITATION"
    )
