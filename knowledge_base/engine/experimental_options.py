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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from knowledge_base.schemas.experimental_option import (
    ExperimentalOption,
    ExperimentalTrial,
    UaSiteDetail,
)
from knowledge_base.engine.trial_outlook import score_trial


_DEFAULT_TTL_DAYS = 7


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
    line_of_therapy: Optional[int] = None
    max_results: int = 10

    def signature(self) -> str:
        """Stable hash for in-process + on-disk caching."""
        joined = "|".join([
            self.disease_term.strip().lower(),
            self.biomarker_term.strip().lower(),
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


def enumerate_experimental_options(
    *,
    disease_id: str,
    disease_term: str,
    biomarker_profile: Optional[str] = None,
    stage_stratum: Optional[str] = None,
    line_of_therapy: Optional[int] = None,
    search_fn: Optional[SearchFn] = None,
    max_results: int = 10,
    cache: bool = True,
    cache_root: Optional[Path] = None,
    cache_ttl_days: int = _DEFAULT_TTL_DAYS,
) -> ExperimentalOption:
    """Return an `ExperimentalOption` bundle for one (disease, biomarker,
    stage, line) scenario.

    Args:
        disease_id:        KB disease id (e.g. "DIS-NSCLC")
        disease_term:      plain-text condition for ctgov (e.g. "Non-small cell lung cancer")
        biomarker_profile: optional biomarker term (e.g. "EGFR mutation")
        stage_stratum:     optional stage tag passed through to the bundle
        line_of_therapy:   optional 1/2/3+ — included in cache key
        search_fn:         injected ctgov-search callable; when None,
                           the bundle returns empty and notes "ctgov
                           search not configured" (offline-friendly)
        max_results:       trials to retrieve
        cache:             when True, reuse a same-signature result
                           from in-process cache

    Returns:
        ExperimentalOption with up-to-`max_results` trials, filtered to
        enrollment-open status. Always returns an `ExperimentalOption`
        — never raises on offline / API failure (per plan §3.3).
    """

    query = TrialQuery(
        disease_term=disease_term,
        biomarker_term=biomarker_profile or "",
        line_of_therapy=line_of_therapy,
        max_results=max_results,
    )
    sig = query.signature()

    if cache and sig in _QUERY_CACHE:
        return _QUERY_CACHE[sig].option

    if cache and cache_root is not None:
        disk_hit = _read_disk_cache(Path(cache_root), sig, cache_ttl_days)
        if disk_hit is not None:
            _QUERY_CACHE[sig] = _CacheEntry(
                when=datetime.now(timezone.utc), option=disk_hit
            )
            return disk_hit

    # Stable id derived from disease + biomarker + line + sync month
    sync_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sync_month = sync_ts[:7]
    bm_slug = (biomarker_profile or "ALL").upper().replace(" ", "_")
    line_slug = f"L{line_of_therapy}" if line_of_therapy else "ALL"
    option_id = f"EXPER-{disease_id}-{bm_slug}-{line_slug}-{sync_month}"

    if search_fn is None:
        return ExperimentalOption(
            id=option_id,
            disease_id=disease_id,
            molecular_subtype=biomarker_profile,
            stage_stratum=stage_stratum,
            line_of_therapy=line_of_therapy,
            trials=[],
            last_synced=sync_ts,
            notes="ctgov search not configured — pass search_fn to enumerate trials.",
        )

    try:
        raw_studies = search_fn(
            condition=disease_term,
            intervention=biomarker_profile or "",
            status="recruiting",
            max_results=max_results,
        )
    except Exception as exc:
        return ExperimentalOption(
            id=option_id,
            disease_id=disease_id,
            molecular_subtype=biomarker_profile,
            stage_stratum=stage_stratum,
            line_of_therapy=line_of_therapy,
            trials=[],
            last_synced=sync_ts,
            notes=f"ctgov search failed: {exc}",
        )

    trials: list[ExperimentalTrial] = []
    for study in (raw_studies or []):
        t = _to_trial(study, sync_ts=sync_ts, biomarker_term=biomarker_profile)
        if t is not None:
            trials.append(t)

    option = ExperimentalOption(
        id=option_id,
        disease_id=disease_id,
        molecular_subtype=biomarker_profile,
        stage_stratum=stage_stratum,
        line_of_therapy=line_of_therapy,
        trials=trials,
        last_synced=sync_ts,
        notes=None,
    )

    if cache:
        _QUERY_CACHE[sig] = _CacheEntry(when=datetime.now(timezone.utc), option=option)
        if cache_root is not None:
            _write_disk_cache(Path(cache_root), sig, option)

    return option


def clear_cache() -> None:
    """Test-only helper to reset the in-process cache."""
    _QUERY_CACHE.clear()
