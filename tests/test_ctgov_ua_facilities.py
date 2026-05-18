"""UA facility extraction — Gap 2 from `docs/reviews/ctgov-wiring-audit-2026-05-18.md`.

Closes the gap where `_ua_sites_from_countries` returned a binary
`["UA"]` marker and discarded city / facility / per-site status. New
shape: structured `UaSiteDetail` list on `ExperimentalTrial`, surfaced
in render.

Coverage across all 4 layers touched:

1. Schema  — `UaSiteDetail` model + `ua_sites_detail` field default
2. Client  — `_parse_study` builds structured `locations` list from
   flat parallel arrays AND from the `contactsLocationsModule` shape;
   `LocationCity` / `LocationFacility` / `LocationStatus` added to
   `_FIELDS`.
3. Engine  — `_ua_sites_detail_from_locations` filters to UA records;
   `_to_trial` wires it through; legacy `sites_ua` binary marker still
   populated for cache-shape backward compat.
4. Render  — `_render_ua_sites` shows city / facility / status when
   `ua_sites_detail` present; falls back to binary badge for old cached
   records.
"""

from __future__ import annotations

from knowledge_base.schemas.experimental_option import (
    ExperimentalTrial,
    UaSiteDetail,
)
from knowledge_base.clients.ctgov_client import _FIELDS, _parse_study
from knowledge_base.engine.experimental_options import (
    _is_ua_country,
    _to_trial,
    _ua_sites_detail_from_locations,
    _ua_sites_from_countries,
)
from knowledge_base.engine.render import _render_ua_sites


# ── Schema ───────────────────────────────────────────────────────────────


def test_ua_sites_detail_defaults_to_empty_list():
    t = ExperimentalTrial(nct_id="NCT01234567", title="t", status="RECRUITING")
    assert t.ua_sites_detail == []


def test_ua_sites_detail_round_trip():
    sites = [
        UaSiteDetail(facility="Kyiv City Cancer Hospital", city="Kyiv",
                     status="RECRUITING"),
        UaSiteDetail(facility="LDS", city="Lviv", status="ACTIVE_NOT_RECRUITING"),
    ]
    t = ExperimentalTrial(
        nct_id="NCT01234567",
        title="t",
        status="RECRUITING",
        ua_sites_detail=sites,
    )
    dumped = t.model_dump()
    reloaded = ExperimentalTrial.model_validate(dumped)
    assert len(reloaded.ua_sites_detail) == 2
    assert reloaded.ua_sites_detail[0].city == "Kyiv"
    assert reloaded.ua_sites_detail[1].status == "ACTIVE_NOT_RECRUITING"


def test_legacy_cached_trial_loads_without_ua_sites_detail():
    """Old cache JSONs predate this field. They must still load —
    `ua_sites_detail` is optional with empty-list default."""
    legacy_payload = {
        "nct_id": "NCT01234567",
        "title": "Legacy",
        "status": "RECRUITING",
        "countries": ["Ukraine"],
        "sites_ua": ["UA"],
    }
    t = ExperimentalTrial.model_validate(legacy_payload)
    assert t.ua_sites_detail == []
    assert t.sites_ua == ["UA"]


# ── Client _parse_study ──────────────────────────────────────────────────


def test_fields_request_includes_location_detail():
    """Without LocationCity / LocationFacility / LocationStatus in the
    field list, ctgov returns only country names and the new fields stay
    empty. This guards against a future drop of those fields."""
    for f in ("LocationCity", "LocationFacility", "LocationStatus"):
        assert f in _FIELDS, f"`{f}` must be requested via fields= "


def test_parse_study_flat_arrays_zipped_into_locations():
    """Search-mode response shape: parallel flat arrays."""
    raw = {
        "NCTId": "NCT99999991",
        "BriefTitle": "Test",
        "OverallStatus": "RECRUITING",
        "LocationCountry": ["Ukraine", "Poland"],
        "LocationCity":    ["Kyiv",    "Warsaw"],
        "LocationFacility": ["Kyiv Cancer Center", "Warsaw Clinic"],
        "LocationStatus":   ["RECRUITING", "RECRUITING"],
    }
    parsed = _parse_study(raw)
    assert parsed["locations"] == [
        {"country": "Ukraine", "city": "Kyiv", "facility": "Kyiv Cancer Center",
         "status": "RECRUITING"},
        {"country": "Poland", "city": "Warsaw", "facility": "Warsaw Clinic",
         "status": "RECRUITING"},
    ]
    # Countries de-duped while preserving order:
    assert parsed["countries"] == ["Ukraine", "Poland"]


def test_parse_study_uneven_flat_arrays_pad_with_none():
    """Real ctgov responses sometimes drop city tags on a subset of
    sites. Zip must pad shorter arrays with None, not truncate."""
    raw = {
        "NCTId": "NCT99999992",
        "BriefTitle": "t",
        "OverallStatus": "RECRUITING",
        "LocationCountry": ["Ukraine", "Ukraine", "Poland"],
        "LocationCity":    ["Kyiv"],  # only one city tag
        "LocationFacility": ["A"],     # only one facility
        "LocationStatus":   [],
    }
    parsed = _parse_study(raw)
    assert len(parsed["locations"]) == 3
    assert parsed["locations"][0]["city"] == "Kyiv"
    assert parsed["locations"][1]["city"] is None
    assert parsed["locations"][2]["country"] == "Poland"


def test_parse_study_full_record_shape_via_locations_module():
    """Full-record-mode response (get_trial): nested structured locations."""
    raw = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT99999993", "briefTitle": "t"},
            "statusModule":         {"overallStatus": "RECRUITING"},
            "contactsLocationsModule": {
                "locations": [
                    {"country": "Ukraine", "city": "Lviv",
                     "facility": "Lviv State Oncology", "status": "RECRUITING"},
                    {"country": "Germany", "city": "Berlin",
                     "facility": "Charité", "status": "ACTIVE_NOT_RECRUITING"},
                ]
            },
        }
    }
    parsed = _parse_study(raw)
    assert parsed["locations"][0]["city"] == "Lviv"
    assert parsed["locations"][0]["status"] == "RECRUITING"
    assert parsed["countries"] == ["Ukraine", "Germany"]


# ── Engine helpers ───────────────────────────────────────────────────────


def test_is_ua_country_matches_iso2_and_full_name_case_insensitive():
    assert _is_ua_country("UA")
    assert _is_ua_country("ua")
    assert _is_ua_country("Ukraine")
    assert _is_ua_country("UKRAINE")
    assert not _is_ua_country("US")
    assert not _is_ua_country("United States")
    assert not _is_ua_country(None)
    assert not _is_ua_country("")


def test_ua_sites_from_countries_legacy_binary_marker_preserved():
    """Old-shape helper still returns ["UA"] / [] — used for cache-shape
    backward compat."""
    assert _ua_sites_from_countries(["US", "Ukraine"]) == ["UA"]
    assert _ua_sites_from_countries(["US"]) == []
    assert _ua_sites_from_countries([]) == []


def test_ua_sites_detail_filters_non_ua_locations():
    locations = [
        {"country": "Ukraine", "city": "Kyiv", "facility": "Kyiv X", "status": "RECRUITING"},
        {"country": "Poland",  "city": "Warsaw", "facility": "Warsaw Y", "status": "RECRUITING"},
        {"country": "UA",      "city": "Lviv", "facility": "Lviv Z", "status": "ACTIVE_NOT_RECRUITING"},
    ]
    out = _ua_sites_detail_from_locations(locations)
    assert len(out) == 2
    assert out[0].city == "Kyiv"
    assert out[1].city == "Lviv"
    assert out[1].status == "ACTIVE_NOT_RECRUITING"


def test_ua_sites_detail_empty_when_no_ua_sites():
    assert _ua_sites_detail_from_locations([]) == []
    assert _ua_sites_detail_from_locations(
        [{"country": "US", "city": "Boston"}]
    ) == []


def test_ua_sites_detail_tolerates_missing_subfields():
    """ctgov sometimes returns a location with only country populated."""
    out = _ua_sites_detail_from_locations(
        [{"country": "Ukraine"}]
    )
    assert len(out) == 1
    assert out[0].city is None
    assert out[0].facility is None
    assert out[0].status is None


# ── _to_trial integration ────────────────────────────────────────────────


def test_to_trial_populates_both_legacy_marker_and_detail():
    """One trial-record round-trip: structured locations in, both
    `sites_ua` (legacy) and `ua_sites_detail` (new) out."""
    study = {
        "nct_id": "NCT99999994",
        "title": "t",
        "status": "RECRUITING",
        "phase": "PHASE2",
        "sponsor": "S",
        "summary": "",
        "eligibility_criteria": "Inclusion Criteria: foo",
        "countries": ["Ukraine", "Poland"],
        "locations": [
            {"country": "Ukraine", "city": "Kyiv", "facility": "F1",
             "status": "RECRUITING"},
            {"country": "Poland", "city": "Warsaw"},
        ],
    }
    t = _to_trial(study, sync_ts="2026-05-18")
    assert t is not None
    assert t.sites_ua == ["UA"]   # legacy marker preserved
    assert len(t.ua_sites_detail) == 1
    assert t.ua_sites_detail[0].facility == "F1"
    assert t.ua_sites_detail[0].city == "Kyiv"


# ── Render ───────────────────────────────────────────────────────────────


def test_render_ua_sites_shows_city_and_facility_when_detail_present():
    t = ExperimentalTrial(
        nct_id="NCT01234567", title="t", status="RECRUITING",
        sites_ua=["UA"],
        ua_sites_detail=[
            UaSiteDetail(facility="Kyiv Cancer Center", city="Kyiv",
                         status="RECRUITING"),
        ],
    )
    out = _render_ua_sites(t, target_lang="uk")
    assert "Kyiv" in out
    assert "Kyiv Cancer Center" in out
    assert "RECRUITING" in out
    assert "badge--ua" in out  # badge still emitted as the visual anchor


def test_render_ua_sites_falls_back_to_binary_badge_when_no_detail():
    """Legacy cached trial: only sites_ua = ['UA'], no detail. Render
    must keep the old badge behavior so existing cache renders unchanged."""
    t = ExperimentalTrial(
        nct_id="NCT01234567", title="t", status="RECRUITING",
        sites_ua=["UA"],
        ua_sites_detail=[],
    )
    out = _render_ua_sites(t, target_lang="uk")
    assert "badge--ua" in out
    assert "<ul" not in out  # no detail list


def test_render_ua_sites_emits_dash_for_non_ua_trial():
    t = ExperimentalTrial(
        nct_id="NCT01234567", title="t", status="RECRUITING",
        sites_ua=[],
        ua_sites_detail=[],
    )
    assert _render_ua_sites(t, target_lang="uk") == "—"


def test_render_ua_sites_collapses_empty_fields():
    """When only country was known for a UA site (no city, no facility),
    render still shows something usable."""
    t = ExperimentalTrial(
        nct_id="NCT01234567", title="t", status="RECRUITING",
        sites_ua=["UA"],
        ua_sites_detail=[UaSiteDetail()],  # all fields None
    )
    out = _render_ua_sites(t, target_lang="uk")
    assert "Ukraine" in out
    assert "<ul" in out
