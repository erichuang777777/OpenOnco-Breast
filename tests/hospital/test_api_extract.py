"""Tests for POST /api/v1/extract (LLM extraction endpoint)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestExtractionEndpoint:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty_extraction(self, client, hcp_headers):
        """Without ANTHROPIC_API_KEY, extraction returns empty but does not crash."""
        resp = await client.post(
            "/api/v1/extract",
            json={"text": "55歲女性，HER2陽性乳癌，第四期，第一線治療。ER陽性。"},
            headers=hcp_headers,
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "conversation_id" in data
            assert data["status"] in ("complete", "needs_clarification")

    @pytest.mark.asyncio
    async def test_short_text_rejected(self, client, hcp_headers):
        resp = await client.post(
            "/api/v1/extract",
            json={"text": "hi"},
            headers=hcp_headers,
        )
        assert resp.status_code == 422  # min_length=5 validation

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/extract",
            json={"text": "55歲女性 HER2陽性乳癌"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_mocked_extraction_complete(self, client, hcp_headers):
        mock_response = {
            "disease_id": "DIS-BREAST",
            "er_status": "positive",
            "her2_status": "positive",
            "her2_ihc": "3+",
            "her2_ish": None,
            "pr_status": "negative",
            "stage_group": "IV",
            "line_of_therapy": 1,
            "ecog": 1,
            "age": 55,
            "sex": "female",
            "brain_mets": None,
            "brca1": None,
            "brca2": None,
            "pik3ca_mutation": None,
            "esr1_mutation": None,
            "pdl1_cps": None,
        }
        with patch(
            "hospital.services.extraction_service._call_llm_extract",
            new=AsyncMock(return_value=mock_response),
        ):
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "55歲女性，HER2陽性 IHC 3+，ER陽性，第四期轉移性乳癌，第一線"},
                headers=hcp_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["patient"]["her2_status"] == "positive"
        assert data["patient"]["stage_group"] == "IV"
        assert data["patient"]["disease_id"] == "DIS-BREAST"

    @pytest.mark.asyncio
    async def test_missing_stage_triggers_clarification(self, client, hcp_headers):
        """Missing Tier 1 field (stage_group) should trigger clarification."""
        incomplete = {
            "disease_id": "DIS-BREAST",
            "er_status": "positive",
            "her2_status": "positive",
            "stage_group": None,  # missing
            "line_of_therapy": 1,
            # rest null
            "her2_ihc": None, "her2_ish": None, "pr_status": None,
            "ecog": None, "age": None, "sex": None,
            "brain_mets": None, "brca1": None, "brca2": None,
            "pik3ca_mutation": None, "esr1_mutation": None, "pdl1_cps": None,
        }
        with patch(
            "hospital.services.extraction_service._call_llm_extract",
            new=AsyncMock(return_value=incomplete),
        ):
            resp = await client.post(
                "/api/v1/extract",
                json={"text": "HER2陽性乳癌，ER陽性，第一線"},
                headers=hcp_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "needs_clarification"
        assert data["missing_field"] == "stage_group"
        assert data["question"] is not None

    @pytest.mark.asyncio
    async def test_conversation_continues_with_id(self, client, hcp_headers):
        """Second turn with conversation_id should merge answers."""
        first_extraction = {
            "disease_id": "DIS-BREAST", "er_status": "positive",
            "her2_status": "positive", "stage_group": None,
            "line_of_therapy": 1, "her2_ihc": None, "her2_ish": None,
            "pr_status": None, "ecog": None, "age": None, "sex": None,
            "brain_mets": None, "brca1": None, "brca2": None,
            "pik3ca_mutation": None, "esr1_mutation": None, "pdl1_cps": None,
        }
        second_extraction = {**first_extraction, "stage_group": "IV"}

        with patch(
            "hospital.services.extraction_service._call_llm_extract",
            new=AsyncMock(return_value=first_extraction),
        ):
            resp1 = await client.post(
                "/api/v1/extract",
                json={"text": "HER2+ ER+ 乳癌 第一線"},
                headers=hcp_headers,
            )
        conv_id = resp1.json()["conversation_id"]

        with patch(
            "hospital.services.extraction_service._call_llm_extract",
            new=AsyncMock(return_value=second_extraction),
        ):
            resp2 = await client.post(
                "/api/v1/extract",
                json={"text": "第四期", "conversation_id": conv_id},
                headers=hcp_headers,
            )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["patient"]["stage_group"] == "IV"
