"""Tests for POST /api/v1/plan and /api/v1/plan/gaps."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_breast_patient(
    her2="positive", er="positive", stage="IV", line=1
) -> dict:
    return {
        "patient": {
            "patient_id": "MRN-001",
            "disease": {"id": "DIS-BREAST"},
            "line_of_therapy": line,
            "demographics": {"age": 55, "sex": "female", "ecog": 1},
            "findings": {
                "her2_status": her2,
                "er_status": er,
                "stage_group": stage,
            },
        }
    }


def _mock_plan_result(plan_id="PLAN-001", indication="IND-BREAST-HER2-POS-MET-1L-THP"):
    track = MagicMock()
    track.track_id = "T1"
    track.label = "THP 1L"
    track.label_en = "THP 1L"
    track.is_default = True
    track.indication_id = indication
    track.selection_reason = None
    track.regimen_data = {
        "id": "REG-THP", "name": "THP",
        "sources": ["SRC-NCCN-BREAST-2025"],
    }
    track.indication_data = {
        "nccn_category": "1",
        "evidence_level": "high",
        "expected_outcomes": {"median_overall_survival_months": 57},
    }

    plan = MagicMock()
    plan.id = plan_id
    plan.version = 1
    plan.tracks = [track]

    result = MagicMock()
    result.plan = plan
    result.disease_id = "DIS-BREAST"
    result.algorithm_id = "ALGO-BREAST-1L"
    result.default_indication_id = indication
    result.warnings = []
    result.trace = []
    return result


class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_valid_her2_positive_patient(self, client, hcp_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result(),
        ):
            resp = await client.post(
                "/api/v1/plan",
                json=_make_breast_patient(),
                headers=hcp_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["disease_id"] == "DIS-BREAST"
        assert len(data["tracks"]) >= 1
        assert data["tracks"][0]["is_default"] is True

    @pytest.mark.asyncio
    async def test_plan_id_in_response(self, client, hcp_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result("PLAN-XYZ"),
        ):
            resp = await client.post(
                "/api/v1/plan",
                json=_make_breast_patient(),
                headers=hcp_headers,
            )
        assert resp.json()["plan_id"] == "PLAN-XYZ"

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client):
        resp = await client.post("/api/v1/plan", json=_make_breast_patient())
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_engine_error_returns_422(self, client, hcp_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            side_effect=ValueError("No algorithm found"),
        ):
            resp = await client.post(
                "/api/v1/plan",
                json=_make_breast_patient(),
                headers=hcp_headers,
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_include_gaps_field_present(self, client, hcp_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result(),
        ):
            body = _make_breast_patient()
            body["include_gaps"] = True
            resp = await client.post(
                "/api/v1/plan", json=body, headers=hcp_headers
            )
        assert "gaps" in resp.json()

    @pytest.mark.asyncio
    async def test_tumor_board_role_allowed(self, client, board_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result(),
        ):
            resp = await client.post(
                "/api/v1/plan",
                json=_make_breast_patient(),
                headers=board_headers,
            )
        assert resp.status_code == 200


class TestDecisionGaps:
    @pytest.mark.asyncio
    async def test_gaps_endpoint_returns_list(self, client, hcp_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result(),
        ):
            resp = await client.post(
                "/api/v1/plan/gaps",
                json=_make_breast_patient(),
                headers=hcp_headers,
            )
        assert resp.status_code == 200
        assert "gaps" in resp.json()
        assert isinstance(resp.json()["gaps"], list)

    @pytest.mark.asyncio
    async def test_gap_item_has_required_fields(self, client, hcp_headers):
        brca_gap_result = _mock_plan_result("IND-BREAST-BRCA-POS-MET-PARPI")
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            side_effect=[_mock_plan_result(), brca_gap_result],
        ):
            resp = await client.post(
                "/api/v1/plan/gaps",
                json=_make_breast_patient(),
                headers=hcp_headers,
            )
        gaps = resp.json().get("gaps", [])
        if gaps:
            gap = gaps[0]
            assert "field" in gap
            assert "tier" in gap
            assert "rationale" in gap
