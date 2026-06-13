"""Pydantic schemas for the guideline-flowchart endpoints.

These are *visualization* DTOs: a node/edge graph derived from an
Algorithm `decision_tree`, plus an optional engine-trace overlay marking
the path a given patient walked. No clinical decision is made here
(CHARTER §8.3) — the graph mirrors already-authored YAML.
"""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel


class GuidelineNode(BaseModel):
    id: str
    kind: str  # start | decision | indication | no_indication
    label: str
    step: Optional[Union[int, str]] = None
    match: Optional[str] = None  # all | any | single (decision nodes)
    conditions: list[str] = []
    red_flags: list[str] = []
    notes: Optional[str] = None
    indication_id: Optional[str] = None
    regimen_name: Optional[str] = None
    nccn_category: Optional[str] = None
    evidence_level: Optional[str] = None
    on_path: bool = False


class GuidelineEdge(BaseModel):
    source: str
    target: str
    branch: Optional[str] = None  # true | false | None
    label: Optional[str] = None
    on_path: bool = False


class GuidelineGraph(BaseModel):
    algorithm_id: str
    disease_id: Optional[str] = None
    line_of_therapy: Optional[Union[int, str]] = None
    purpose: Optional[str] = None
    default_indication: Optional[str] = None
    alternative_indication: Optional[str] = None
    sources: list[str] = []
    nodes: list[GuidelineNode] = []
    edges: list[GuidelineEdge] = []
    has_trace: bool = False


class GuidelineSummary(BaseModel):
    algorithm_id: str
    disease_id: Optional[str] = None
    line_of_therapy: Optional[Union[int, str]] = None
    purpose: Optional[str] = None


class GuidelineListResponse(BaseModel):
    algorithms: list[GuidelineSummary] = []
