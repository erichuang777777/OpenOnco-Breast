"""Cited-trials status render — Gap 3 finale.

Closes the render layer of Gap 3 from
`docs/reviews/ctgov-wiring-audit-2026-05-18.md`. The foundation
(extraction + cache + badge) shipped in the parent PR; this layer
decorates Plan output with a "Cited trials — current status" section.

Coverage:

1. `_render_cited_trials_status` extracts NCTs from input HTML, looks
   up cached badges, emits a section with status badges (link to
   ctgov, recruiting / closed colour class, last-synced date).
2. Section is suppressed when no NCTs cited, or when none have
   cached status (silent fallback — never invent placeholder content).
3. Badge colour class differs for recruiting vs closed trials.
4. Render-time only (CHARTER §8.3): no engine routing side effect.
"""

from __future__ import annotations

from pathlib import Path

from knowledge_base.engine.citation_enrichment import save_study_to_cache
from knowledge_base.engine.render import _render_cited_trials_status


def test_empty_body_returns_empty_string(tmp_path: Path):
    assert _render_cited_trials_status("", "uk", cache_root=tmp_path) == ""


def test_no_ncts_in_body_returns_empty_string(tmp_path: Path):
    body = "<section><p>Some clinical text without trial citations.</p></section>"
    assert _render_cited_trials_status(body, "uk", cache_root=tmp_path) == ""


def test_nct_cited_but_no_cache_suppresses_section(tmp_path: Path):
    """Conservative fallback: when an NCT appears in the rendered body
    but the per-NCT cache has nothing, suppress the section rather than
    show a placeholder. Avoids implying the data was looked up when it
    wasn't."""
    body = "<p>KEYNOTE-024 (NCT02220894) showed OS benefit.</p>"
    out = _render_cited_trials_status(body, "uk", cache_root=tmp_path)
    assert out == ""


def test_renders_recruiting_badge(tmp_path: Path):
    save_study_to_cache(
        "NCT04001023",
        {"nct_id": "NCT04001023", "status": "RECRUITING", "phase": "PHASE3"},
        cache_root=tmp_path,
    )
    body = '<p>Trial reference: NCT04001023</p>'
    out = _render_cited_trials_status(body, "uk", cache_root=tmp_path)
    assert "cited-trials-status" in out
    assert "NCT04001023" in out
    assert "trial-status--recruiting" in out
    assert "Recruiting" in out
    assert 'href="https://clinicaltrials.gov/study/NCT04001023"' in out


def test_renders_closed_badge_with_different_class(tmp_path: Path):
    save_study_to_cache(
        "NCT02220894",
        {"status": "COMPLETED"},
        cache_root=tmp_path,
    )
    body = "<p>KEYNOTE-024 (NCT02220894).</p>"
    out = _render_cited_trials_status(body, "uk", cache_root=tmp_path)
    assert "trial-status--closed" in out
    assert "trial-status--recruiting" not in out
    assert "Completed" in out


def test_multiple_ncts_each_get_their_own_row(tmp_path: Path):
    save_study_to_cache(
        "NCT01", {"status": "RECRUITING"}, cache_root=tmp_path
    )
    save_study_to_cache(
        "NCT02", {"status": "COMPLETED"}, cache_root=tmp_path
    )
    save_study_to_cache(
        "NCT03", {"status": "TERMINATED"}, cache_root=tmp_path
    )
    # Use 8-digit NCTs since the extractor requires exactly 8 digits.
    save_study_to_cache("NCT10000001", {"status": "RECRUITING"}, cache_root=tmp_path)
    save_study_to_cache("NCT10000002", {"status": "COMPLETED"},  cache_root=tmp_path)
    save_study_to_cache("NCT10000003", {"status": "TERMINATED"}, cache_root=tmp_path)
    body = (
        "Body mentions NCT10000001, then NCT10000002, then NCT10000003."
    )
    out = _render_cited_trials_status(body, "uk", cache_root=tmp_path)
    assert out.count("<li") == 3
    assert "NCT10000001" in out and "NCT10000002" in out and "NCT10000003" in out


def test_partial_cache_only_shows_what_we_have(tmp_path: Path):
    """Body cites two NCTs but cache only has one. Section appears with
    the one we know; the uncached one is silently dropped."""
    save_study_to_cache(
        "NCT10000001", {"status": "RECRUITING"}, cache_root=tmp_path
    )
    body = "Citing NCT10000001 and NCT99999999."
    out = _render_cited_trials_status(body, "uk", cache_root=tmp_path)
    assert "NCT10000001" in out
    assert "NCT99999999" not in out


def test_last_synced_date_truncated_to_yyyy_mm_dd(tmp_path: Path):
    save_study_to_cache(
        "NCT10000001",
        {"status": "RECRUITING"},
        cache_root=tmp_path,
    )
    out = _render_cited_trials_status(
        "NCT10000001", "uk", cache_root=tmp_path
    )
    # ISO timestamp written by save_study_to_cache → trimmed to date.
    import re
    m = re.search(r'cited-trial-synced">\(([^)]+)\)', out)
    assert m is not None
    # Just yyyy-mm-dd
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', m.group(1))


def test_localized_heading_uk_vs_en(tmp_path: Path):
    save_study_to_cache(
        "NCT10000001", {"status": "RECRUITING"}, cache_root=tmp_path
    )
    uk = _render_cited_trials_status("NCT10000001", "uk", cache_root=tmp_path)
    en = _render_cited_trials_status("NCT10000001", "en", cache_root=tmp_path)
    assert "Цитовані випробування" in uk
    assert "Cited trials" in en
