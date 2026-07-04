"""Tests for GET /api/v1/plan/{plan_id} — plan persistence + retrieval.

Context: docs/reviews/physician-platform-review-2026-06-13.md found that
`ClinicPage` (frontend) calls `GET /api/v1/plan/{plan_id}` to reload a
saved plan, but no server-side handler existed, and `POST /plan` never
persisted a plan anywhere for one to find. This closes both halves:
`POST /plan` (and `POST /plan/{id}/revise`) now persist via
`plan_service.persist_plan`, and this new `GET /plan/{id}` retrieves it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_breast_patient(patient_id="MRN-001") -> dict:
    return {
        "patient": {
            "patient_id": patient_id,
            "disease": {"id": "DIS-BREAST"},
            "line_of_therapy": 1,
            "demographics": {"age": 55, "sex": "female", "ecog": 1},
            "findings": {
                "her2_status": "positive",
                "er_status": "positive",
                "stage_group": "IV",
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


class TestGetPlan:
    @pytest.mark.asyncio
    async def test_generated_plan_can_be_reloaded(self, client, hcp_headers):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result("PLAN-RELOAD-1"),
        ):
            create_resp = await client.post(
                "/api/v1/plan",
                json=_make_breast_patient(),
                headers=hcp_headers,
            )
        assert create_resp.status_code == 200
        plan_id = create_resp.json()["plan_id"]

        get_resp = await client.get(
            f"/api/v1/plan/{plan_id}", headers=hcp_headers
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["plan_id"] == plan_id
        assert data["disease_id"] == "DIS-BREAST"
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["is_default"] is True

    @pytest.mark.asyncio
    async def test_unknown_plan_id_returns_404(self, client, hcp_headers):
        resp = await client.get(
            "/api/v1/plan/PLAN-DOES-NOT-EXIST", headers=hcp_headers
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "PLAN_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client):
        resp = await client.get("/api/v1/plan/PLAN-001")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_plan_without_patient_id_is_not_persisted_but_create_still_succeeds(
        self, client, hcp_headers
    ):
        """A plan generated with no patient_id anywhere has no MRN to key
        storage on — create_plan must still succeed (degraded: just not
        reloadable), not 500."""
        body = _make_breast_patient(patient_id=None)
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result("PLAN-NO-MRN"),
        ):
            create_resp = await client.post(
                "/api/v1/plan", json=body, headers=hcp_headers
            )
        assert create_resp.status_code == 200

        get_resp = await client.get(
            "/api/v1/plan/PLAN-NO-MRN", headers=hcp_headers
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_revised_plan_supersedes_original_and_both_retrievable(
        self, client, hcp_headers
    ):
        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result("PLAN-V1"),
        ):
            create_resp = await client.post(
                "/api/v1/plan", json=_make_breast_patient(), headers=hcp_headers
            )
        assert create_resp.status_code == 200

        with patch(
            "hospital.decision.services.plan_service.generate_plan",
            return_value=_mock_plan_result("PLAN-V2"),
        ):
            revise_resp = await client.post(
                "/api/v1/plan/PLAN-V1/revise",
                json={
                    **_make_breast_patient(),
                    "revision_trigger": "New biopsy results changed staging",
                },
                headers=hcp_headers,
            )
        assert revise_resp.status_code == 200

        # Both versions remain independently retrievable.
        v1 = await client.get("/api/v1/plan/PLAN-V1", headers=hcp_headers)
        v2 = await client.get("/api/v1/plan/PLAN-V2", headers=hcp_headers)
        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.json()["plan_id"] == "PLAN-V1"
        assert v2.json()["plan_id"] == "PLAN-V2"


class TestPersistPlanService:
    @pytest.mark.asyncio
    async def test_persist_and_get_stored_plan_round_trip(self, db_session):
        from hospital.decision.schemas.plan import PlanResponse, TrackResponse
        from hospital.decision.services.plan_service import (
            get_stored_plan,
            persist_plan,
        )

        response = PlanResponse(
            plan_id="PLAN-UNIT-1",
            disease_id="DIS-BREAST",
            algorithm_id="ALGO-BREAST-1L",
            tracks=[
                TrackResponse(
                    track_id="T1",
                    label="Track 1",
                    is_default=True,
                    indication_id="IND-X",
                )
            ],
        )
        await persist_plan(
            db_session, response, mrn="MRN-UNIT-1", created_by="user-001"
        )

        found = await get_stored_plan(db_session, "PLAN-UNIT-1")
        assert found is not None
        stored, mrn = found
        assert stored.plan_id == "PLAN-UNIT-1"
        assert stored.tracks[0].track_id == "T1"
        assert mrn == "MRN-UNIT-1"

    @pytest.mark.asyncio
    async def test_get_stored_plan_returns_none_for_unknown_id(self, db_session):
        from hospital.decision.services.plan_service import get_stored_plan

        assert await get_stored_plan(db_session, "PLAN-NOPE") is None

    @pytest.mark.asyncio
    async def test_supersedes_marks_prior_plan_superseded(self, db_session):
        from hospital.db.models import Plan as PlanRow
        from hospital.decision.schemas.plan import PlanResponse, TrackResponse
        from hospital.decision.services.plan_service import persist_plan

        original = PlanResponse(
            plan_id="PLAN-ORIG",
            disease_id="DIS-BREAST",
            tracks=[TrackResponse(track_id="T1", label="L", is_default=True, indication_id="IND-X")],
        )
        await persist_plan(
            db_session, original, mrn="MRN-1", created_by="user-001"
        )

        revised = PlanResponse(
            plan_id="PLAN-REVISED",
            disease_id="DIS-BREAST",
            tracks=[TrackResponse(track_id="T1", label="L", is_default=True, indication_id="IND-Y")],
        )
        await persist_plan(
            db_session,
            revised,
            mrn="MRN-1",
            created_by="user-001",
            supersedes="PLAN-ORIG",
        )
        await db_session.flush()

        prior = await db_session.get(PlanRow, "PLAN-ORIG")
        new = await db_session.get(PlanRow, "PLAN-REVISED")
        assert prior.status == "superseded"
        assert prior.superseded_by == "PLAN-REVISED"
        assert new.supersedes == "PLAN-ORIG"
        assert new.version == 2
