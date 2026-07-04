"""Experimental-options enumerator — third Plan track.

Per docs/plans/ua_ingestion_and_alternatives_2026-04-26.md §3.3.

Translates a (disease, biomarker_profile, stage, line_of_therapy) tuple
into a list of currently-recruiting clinical trials, exposed as an
`ExperimentalOption` for the render layer.

Architectural notes:
  - Engine selection (default + alternative tracks) is unaffected. This
    module is consumed *after* `generate_plan()` settles the engine
    decision; `experimental_options` is appended metadata, never a
    selection signal. (See `feedback_efficacy_over_registration.md`.)
  - The ctgov client is injected so tests + offline runs use a stub.
    Pyodide cannot reach api.clinicaltrials.gov directly — production
    will sync server-side and bake results into the engine bundle, or
    fetch via the OncoKB-style proxy at `services/`.
  - In-process query cache is a plain dict keyed by query signature; a
    7-day on-disk TTL cache is a follow-up (Phase C §5.4 task 2).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from knowledge_base.schemas.experimental_option import (
    ExperimentalOption,
    ExperimentalTrial,
    TrialOutlook,
    UaSiteDetail,
)
from knowledge_base.engine.trial_outlook import detect_age_sex_screen, score_trial


_DEFAULT_TTL_DAYS = 7

# Courtesy delay between successive per-biomarker ctgov calls within one
# multi-biomarker enumerate_experimental_options() invocation (see the
# fan-out loop below). Matches the spacing already used elsewhere for
# ctgov courtesy (`ctgov_client.enrich_report_with_trials`).
_MULTI_TERM_SLEEP_SECONDS = 0.15


# Statuses we surface as "experimental option for the patient."
# COMPLETED / TERMINATED / WITHDRAWN are intentionally excluded —
# enrollment is closed.
_OPEN_STATUSES = {"RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION"}


# ── Query → trials ──────────────────────────────────────────────────────


@dataclass
class TrialQuery:
    """Inputs to one ctgov search. Keep in lock-step with
    `enumerate_experimental_options()` parameters so the cache key is
    derivable from the public API."""

    disease_term: str           # plain-text condition (e.g. "Multiple myeloma")
    biomarker_term: str = ""    # plain-text biomarker (e.g. "TP53 mutation"); "" → no filter
    biomarker_terms: tuple[str, ...] = ()  # multi-biomarker case; () → use biomarker_term
    line_of_therapy: Optional[int] = None
    max_results: int = 10

    def signature(self) -> str:
        """Stable hash for in-process + on-disk caching.

        When `biomarker_terms` is empty (the single-biomarker or
        no-biomarker case — still the overwhelming majority of calls),
        this produces byte-identical hashes to the pre-multi-biomarker
        implementation, so existing on-disk cache files stay valid.
        """
        if self.biomarker_terms:
            terms_key = "+".join(
                sorted(t.strip().lower() for t in self.biomarker_terms if t.strip())
            )
        else:
            terms_key = self.biomarker_term.strip().lower()
        joined = "|".join([
            self.disease_term.strip().lower(),
            terms_key,
            str(self.line_of_therapy or ""),
            str(self.max_results),
        ])
        return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


# Type alias for the injected ctgov search function.
# Matches `knowledge_base.clients.ctgov_client.search_trials` signature.
SearchFn = Callable[..., list[dict]]


_UA_COUNTRY_TOKENS = {"UA", "UKRAINE"}


def _is_ua_country(value: object) -> bool:
    """ctgov is inconsistent: search-mode flat fields return full names
    ("Ukraine"), full-record mode returns ISO-2 codes ("UA"). Match
    either, case-insensitively."""
    if not isinstance(value, str):
        return False
    return value.strip().upper() in _UA_COUNTRY_TOKENS


def _ua_sites_from_countries(countries: list[str]) -> list[str]:
    """Binary UA marker, kept for cache-shape backward compat. The
    structured per-site detail lives in `ua_sites_detail` (populated by
    `_ua_sites_detail_from_locations`); this list is now redundant in
    new data but preserved so legacy cached `ExperimentalOption` JSONs
    keep loading.
    """
    if not countries:
        return []
    return ["UA"] if any(_is_ua_country(c) for c in countries) else []


def _ua_sites_detail_from_locations(locations: list) -> list[UaSiteDetail]:
    """Filter a parsed ctgov `locations` list to UA records and convert
    them to `UaSiteDetail`. Empty when the upstream record carried no
    UA site OR when only country-level info was available."""
    if not locations:
        return []
    out: list[UaSiteDetail] = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if not _is_ua_country(loc.get("country")):
            continue
        out.append(
            UaSiteDetail(
                facility=loc.get("facility") or None,
                city=loc.get("city") or None,
                state=loc.get("state") or None,
                status=loc.get("status") or None,
            )
        )
    return out


# Rank used to pick the "best" outlook when the same NCT ID surfaces
# under more than one biomarker search (multi-biomarker patients) —
# `score_trial`'s stratification is scoped to a single biomarker phrase
# (ALL tokens within that phrase must match), so a trial enriched for
# the patient's *second* biomarker but not their first must still show
# as "enriched" rather than being overwritten by the weaker result.
_STRAT_RANK = {"enriched": 2, "unclear": 1, "open_label": 0}


def _outlook_rank(trial: ExperimentalTrial) -> int:
    if trial.outlook is None:
        return -1
    return _STRAT_RANK.get(trial.outlook.biomarker_stratification, 0)


def _to_trial(
    study: dict,
    *,
    sync_ts: str,
    biomarker_term: Optional[str] = None,
) -> Optional[ExperimentalTrial]:
    """Convert one parsed-ctgov study dict into an `ExperimentalTrial`,
    skipping records with closed enrollment or missing NCT id.

    `biomarker_term` flows from the enumerator's `biomarker_profile`
    parameter into `score_trial` for stratification detection. None/empty
    yields an "open_label" stratification.
    """

    status = (study.get("status") or "").upper()
    if status not in _OPEN_STATUSES:
        return None

    nct = study.get("nct_id") or study.get("NCTId") or ""
    if not nct:
        return None

    countries = study.get("countries") or []
    elig = study.get("eligibility_criteria") or study.get("EligibilityCriteria") or ""
    incl, excl = _split_eligibility(elig)

    outlook = score_trial(
        study,
        biomarker_term=biomarker_term,
        inclusion_summary=incl,
        exclusion_summary=excl,
        last_scored=sync_ts,
    )

    raw_locations = study.get("locations") or []
    return ExperimentalTrial(
        nct_id=nct,
        title=study.get("title") or study.get("BriefTitle") or "",
        status=status,
        phase=study.get("phase"),
        sponsor=study.get("sponsor"),
        summary=(study.get("summary") or "")[:600] or None,
        inclusion_summary=incl,
        exclusion_summary=excl,
        min_age=study.get("min_age") or study.get("MinimumAge") or None,
        max_age=study.get("max_age") or study.get("MaximumAge") or None,
        eligible_sex=study.get("sex") or study.get("Sex") or None,
        countries=list(countries) if isinstance(countries, list) else [],
        sites_ua=_ua_sites_from_countries(
            list(countries) if isinstance(countries, list) else []
        ),
        ua_sites_detail=_ua_sites_detail_from_locations(raw_locations),
        sites_global_count=study.get("location_count"),
        last_synced=sync_ts,
        outlook=outlook,
    )


def _split_eligibility(text: str) -> tuple[Optional[str], Optional[str]]:
    """Best-effort split of free-text eligibility criteria into
    inclusion vs exclusion. ctgov stores both in a single block; we
    look for the conventional headings. Returns (None, None) when the
    text doesn't follow the convention — render treats null as "see
    full study record on ctgov."""

    if not text:
        return (None, None)
    norm = text.replace("\r", "")
    lower = norm.lower()
    excl_idx = max(
        lower.find("exclusion criteria"),
        lower.find("exclusions:"),
    )
    if excl_idx < 0:
        return (norm.strip()[:400] or None, None)
    inclusion = norm[:excl_idx].strip()
    exclusion = norm[excl_idx:].strip()
    return (
        (inclusion[:400] or None) if inclusion else None,
        (exclusion[:400] or None) if exclusion else None,
    )


# ── Public entry point ──────────────────────────────────────────────────


@dataclass
class _CacheEntry:
    when: datetime
    option: ExperimentalOption


_QUERY_CACHE: dict[str, _CacheEntry] = {}


def _disk_cache_path(cache_root: Path, sig: str) -> Path:
    return cache_root / f"ctgov_{sig}.json"


def _read_disk_cache(
    cache_root: Path, sig: str, ttl_days: int
) -> Optional[ExperimentalOption]:
    """Return cached `ExperimentalOption` from disk if file exists and the
    `cached_at` timestamp is within TTL. Otherwise return None. Any error
    (missing file, corrupted JSON, schema drift) is swallowed — cache is
    a best-effort optimization, never a correctness requirement."""
    path = _disk_cache_path(cache_root, sig)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(payload["cached_at"])
        if datetime.now(timezone.utc) - cached_at > timedelta(days=ttl_days):
            return None
        return ExperimentalOption.model_validate(payload["option"])
    except (OSError, ValueError, KeyError):
        return None


def _write_disk_cache(
    cache_root: Path, sig: str, option: ExperimentalOption
) -> None:
    """Best-effort write of an `ExperimentalOption` to a per-signature JSON
    file. Failures are silently ignored — engine should not block on cache
    write errors (filesystem full, read-only mount, etc.)."""
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "option": option.model_dump(),
        }
        _disk_cache_path(cache_root, sig).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _apply_patient_screen(
    option: ExperimentalOption,
    patient_age: Optional[float],
    patient_sex: Optional[str],
) -> ExperimentalOption:
    """Overlay a per-patient age/sex eligibility screen onto an
    `ExperimentalOption` — including one that came straight out of the
    in-process or on-disk cache.

    `ExperimentalOption` bundles are cached by (disease, biomarker, line)
    signature and shared across every patient with that signature. The
    trial's own min/max age and sex fields are patient-agnostic facts
    (cached safely on `ExperimentalTrial`); the *comparison* against a
    specific patient's age/sex is not, so it is computed fresh here on
    every call rather than baked into the cached object.

    Returns `option` unchanged (same object identity) when no patient
    demographics are supplied, so callers that don't pass them see zero
    overhead and cache-identity tests keep holding.
    """
    if patient_age is None and not patient_sex:
        return option
    if not option.trials:
        return option

    new_trials = []
    for t in option.trials:
        screen, note = detect_age_sex_screen(
            t.min_age, t.max_age, t.eligible_sex, patient_age, patient_sex
        )
        base = t.outlook
        if base is None:
            new_outlook = TrialOutlook(
                biomarker_stratification="open_label",
                age_sex_screen=screen,
                notes=[note] if note else [],
            )
        else:
            notes = list(base.notes)
            if note:
                notes.append(note)
            new_outlook = base.model_copy(update={"age_sex_screen": screen, "notes": notes})
        new_trials.append(t.model_copy(update={"outlook": new_outlook}))

    return option.model_copy(update={"trials": new_trials})


def enumerate_experimental_options(
    *,
    disease_id: str,
    disease_term: str,
    biomarker_profile: Optional[str] = None,
    biomarker_profiles: Optional[list[str]] = None,
    stage_stratum: Optional[str] = None,
    line_of_therapy: Optional[int] = None,
    patient_age: Optional[float] = None,
    patient_sex: Optional[str] = None,
    search_fn: Optional[SearchFn] = None,
    max_results: int = 20,
    cache: bool = True,
    cache_root: Optional[Path] = None,
    cache_ttl_days: int = _DEFAULT_TTL_DAYS,
) -> ExperimentalOption:
    """Return an `ExperimentalOption` bundle for one (disease, biomarker,
    stage, line) scenario.

    Args:
        disease_id:        KB disease id (e.g. "DIS-NSCLC")
        disease_term:      plain-text condition for ctgov (e.g. "Non-small cell lung cancer")
        biomarker_profile: optional single biomarker term (e.g. "EGFR mutation").
                           Ignored when `biomarker_profiles` is also given.
        biomarker_profiles: optional list of biomarker terms for patients with
                           more than one positive biomarker (e.g. EGFR+ and
                           TP53+). Each term is searched separately — CT.gov's
                           `query.term` Essie syntax technically supports
                           boolean OR, but per-term calls keep the trial-outlook
                           stratification scoped correctly (see `_to_trial` /
                           `score_trial`, which requires ALL tokens of a *single*
                           biomarker phrase to match, not a mix across
                           biomarkers) and avoid depending on undocumented-here
                           Essie query behavior. Results are deduplicated by
                           NCT ID; when a trial surfaces under more than one
                           biomarker, the best (most-specific) stratification
                           wins. Bounded to the first 5 distinct terms to cap
                           API calls for heavily-annotated patients.
        stage_stratum:     optional stage tag passed through to the bundle
        line_of_therapy:   optional 1/2/3+ — included in cache key
        patient_age:       optional patient age in years. NOT part of the
                           cache key (see `_apply_patient_screen`) — used
                           only to compute each trial's `age_sex_screen`
                           overlay for this call.
        patient_sex:       optional patient sex (e.g. "male"/"female").
                           Same non-cached overlay treatment as `patient_age`.
        search_fn:         injected ctgov-search callable; when None,
                           the bundle returns empty and notes "ctgov
                           search not configured" (offline-friendly)
        max_results:       trials to retrieve per biomarker term
        cache:             when True, reuse a same-signature result
                           from in-process cache

    Returns:
        ExperimentalOption with up-to-`max_results` trials per biomarker term
        (deduplicated), filtered to enrollment-open status. Always returns an
        `ExperimentalOption` — never raises on offline / API failure (per
        plan §3.3).
    """

    _MAX_BIOMARKER_TERMS = 5
    if biomarker_profiles:
        # Dedup, drop blanks, preserve order, bound the fan-out.
        terms_list = list(dict.fromkeys(t for t in biomarker_profiles if t))[
            :_MAX_BIOMARKER_TERMS
        ]
    else:
        terms_list = [biomarker_profile] if biomarker_profile else []

    query = TrialQuery(
        disease_term=disease_term,
        biomarker_term=(terms_list[0] if len(terms_list) == 1 else ""),
        biomarker_terms=tuple(terms_list) if len(terms_list) > 1 else (),
        line_of_therapy=line_of_therapy,
        max_results=max_results,
    )
    sig = query.signature()

    if cache and sig in _QUERY_CACHE:
        return _apply_patient_screen(_QUERY_CACHE[sig].option, patient_age, patient_sex)

    if cache and cache_root is not None:
        disk_hit = _read_disk_cache(Path(cache_root), sig, cache_ttl_days)
        if disk_hit is not None:
            _QUERY_CACHE[sig] = _CacheEntry(
                when=datetime.now(timezone.utc), option=disk_hit
            )
            return _apply_patient_screen(disk_hit, patient_age, patient_sex)

    # Stable id derived from disease + biomarker(s) + line + sync month
    sync_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sync_month = sync_ts[:7]
    bm_display = ", ".join(terms_list) if terms_list else None
    bm_slug = (
        "+".join(t.upper().replace(" ", "_") for t in terms_list) if terms_list else "ALL"
    )
    line_slug = f"L{line_of_therapy}" if line_of_therapy else "ALL"
    option_id = f"EXPER-{disease_id}-{bm_slug}-{line_slug}-{sync_month}"

    if search_fn is None:
        return ExperimentalOption(
            id=option_id,
            disease_id=disease_id,
            molecular_subtype=bm_display,
            stage_stratum=stage_stratum,
            line_of_therapy=line_of_therapy,
            trials=[],
            last_synced=sync_ts,
            notes="ctgov search not configured — pass search_fn to enumerate trials.",
        )

    # One search per biomarker term (or a single unfiltered search when the
    # patient has none). Merge-by-NCT-ID so a trial matching more than one
    # biomarker appears once, keeping its best stratification.
    query_terms: list[Optional[str]] = terms_list if terms_list else [None]
    seen_trials: dict[str, ExperimentalTrial] = {}
    search_errors: list[str] = []
    for i, term in enumerate(query_terms):
        # Courtesy spacing between per-biomarker fan-out calls only —
        # ctgov's own rate limiting is the caller's responsibility
        # (`CtgovClient.rate_limit`), but a bare `search_trials` callable
        # has none, and a multi-biomarker patient would otherwise fire
        # several requests back-to-back within one Plan generation.
        if i > 0:
            time.sleep(_MULTI_TERM_SLEEP_SECONDS)
        try:
            raw_studies = search_fn(
                condition=disease_term,
                term=term or "",
                status="open",
                max_results=max_results,
            )
        except Exception as exc:
            search_errors.append(str(exc))
            continue
        for study in (raw_studies or []):
            t = _to_trial(study, sync_ts=sync_ts, biomarker_term=term)
            if t is None:
                continue
            prior = seen_trials.get(t.nct_id)
            if prior is None or _outlook_rank(t) > _outlook_rank(prior):
                seen_trials[t.nct_id] = t

    if search_errors and not seen_trials:
        return ExperimentalOption(
            id=option_id,
            disease_id=disease_id,
            molecular_subtype=bm_display,
            stage_stratum=stage_stratum,
            line_of_therapy=line_of_therapy,
            trials=[],
            last_synced=sync_ts,
            notes=f"ctgov search failed: {'; '.join(search_errors)}",
        )

    notes = None
    if search_errors:
        notes = (
            f"partial ctgov failure ({len(search_errors)}/{len(query_terms)} "
            f"terms): {'; '.join(search_errors)}"
        )

    option = ExperimentalOption(
        id=option_id,
        disease_id=disease_id,
        molecular_subtype=bm_display,
        stage_stratum=stage_stratum,
        line_of_therapy=line_of_therapy,
        trials=list(seen_trials.values()),
        last_synced=sync_ts,
        notes=notes,
    )

    if cache:
        _QUERY_CACHE[sig] = _CacheEntry(when=datetime.now(timezone.utc), option=option)
        if cache_root is not None:
            _write_disk_cache(Path(cache_root), sig, option)

    return _apply_patient_screen(option, patient_age, patient_sex)


def clear_cache() -> None:
    """Test-only helper to reset the in-process cache."""
    _QUERY_CACHE.clear()
