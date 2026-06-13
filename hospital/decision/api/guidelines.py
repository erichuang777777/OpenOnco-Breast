"""Guideline-flowchart API — read-only visualization of Algorithm decision
trees.

    GET /api/v1/guidelines?disease=DIS-BREAST   → list algorithms
    GET /api/v1/guidelines/{algorithm_id}        → node/edge graph

The graph mirrors authored YAML (`decision_tree`); it never makes a
clinical decision (CHARTER §8.3). To overlay the path a specific patient
walked, generate a plan first and POST its trace to `/{id}/trace-overlay`.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.config import get_settings
from hospital.decision.schemas.guideline import (
    GuidelineGraph,
    GuidelineListResponse,
)
from hospital.decision.services import guideline_service

# kb_admin / auditor also need to view guidelines for the audit interface.
GUIDELINE_VIEWER_ROLES = HCP_ROLES + ["kb_admin", "auditor"]

router = APIRouter(prefix="/guidelines", tags=["guidelines"])


@router.get("", response_model=GuidelineListResponse)
async def list_guidelines(
    disease: Optional[str] = Query(None, description="Filter by disease id, e.g. DIS-BREAST"),
    user: dict = Depends(require_role(GUIDELINE_VIEWER_ROLES)),
) -> GuidelineListResponse:
    settings = get_settings()
    algorithms = guideline_service.list_algorithms_for_disease(
        disease, kb_root=settings.kb_root_path
    )
    return GuidelineListResponse(algorithms=algorithms)


@router.get("/{algorithm_id}", response_model=GuidelineGraph)
async def get_guideline_graph(
    algorithm_id: str,
    user: dict = Depends(require_role(GUIDELINE_VIEWER_ROLES)),
) -> GuidelineGraph:
    settings = get_settings()
    graph = guideline_service.build_guideline_graph(
        algorithm_id, kb_root=settings.kb_root_path
    )
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "ALGORITHM_NOT_FOUND", "message": f"No algorithm '{algorithm_id}'."},
        )
    return GuidelineGraph(**graph)
