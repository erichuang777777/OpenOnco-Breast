"""ClinicalTrials.gov proxy endpoint — GET /api/v1/trials

Wraps the existing ctgov_client.search_trials() and exposes it as a
REST endpoint so the frontend can query relevant trials without CORS issues.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from hospital.auth.dependencies import HCP_ROLES, require_role

router = APIRouter(prefix="/trials", tags=["trials"])


class TrialSummary(BaseModel):
    nct_id: str
    title: str
    status: str
    phase: str
    enrollment: int | None
    start_date: str
    completion_date: str
    brief_summary: str
    primary_outcomes: list[str]
    eligibility_summary: str
    age_range: str
    sex: str
    sponsor: str
    countries: list[str]
    site_count: int
    url: str


@router.get("", response_model=list[TrialSummary])
async def search_trials(
    condition: str = Query(..., description="Disease / condition (e.g. 'breast cancer HER2')"),
    intervention: str = Query("", description="Drug or treatment name"),
    trial_status: str = Query("recruiting", alias="status", description="recruiting | active | completed | all"),
    phase: str = Query("", description="Phase filter: 1, 2, 3, or empty for all"),
    max_results: int = Query(10, ge=1, le=25),
    user: dict = Depends(require_role(HCP_ROLES)),
) -> list[TrialSummary]:
    """
    Search ClinicalTrials.gov and return matching studies.

    Results are fetched live from clinicaltrials.gov — expect ~500ms latency.
    The backend imposes a ~10 req/s rate limit inherited from the CT.gov API.
    """
    from knowledge_base.clients.ctgov_client import search_trials as _search

    raw = _search(
        condition=condition,
        intervention=intervention,
        status=trial_status,
        phase=phase,
        max_results=max_results,
    )
    return [
        TrialSummary(
            nct_id=t.get("nct_id", ""),
            title=t.get("title", ""),
            status=t.get("status", ""),
            phase=t.get("phase", ""),
            enrollment=t.get("enrollment") or None,
            start_date=t.get("start_date", ""),
            completion_date=t.get("completion_date", ""),
            brief_summary=t.get("brief_summary", ""),
            primary_outcomes=t.get("primary_outcomes", []),
            eligibility_summary=t.get("eligibility_summary", ""),
            age_range=t.get("age_range", ""),
            sex=t.get("sex", "ALL"),
            sponsor=t.get("sponsor", ""),
            countries=t.get("countries", []),
            site_count=t.get("site_count", 0),
            url=t.get("url", ""),
        )
        for t in raw
    ]
