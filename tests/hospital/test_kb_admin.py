"""Tests for /api/v1/admin/kb/status, /refresh, /crawler-notify."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest

os.environ.setdefault("CRAWLER_WEBHOOK_SECRET", "test-crawler-secret")


def _sign(body: bytes, secret: str = "test-crawler-secret") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestKbStatus:
    @pytest.mark.asyncio
    async def test_admin_can_get_status(self, client, admin_headers, monkeypatch):
        from hospital.admin.api import kb as kb_module
        monkeypatch.setattr(kb_module, "_get_kb_status", lambda: kb_module.KbStatusResponse(
            ok=True, total_entities=100, by_type={"diseases": 10}, schema_errors=0,
            ref_errors=0, contract_errors=0, last_refreshed_at=None,
        ))
        resp = await client.get("/api/v1/admin/kb/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["total_entities"] == 100

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, hcp_headers):
        resp = await client.get("/api/v1/admin/kb/status", headers=hcp_headers)
        assert resp.status_code == 403


class TestKbRefresh:
    @pytest.mark.asyncio
    async def test_admin_can_refresh(self, client, admin_headers, monkeypatch):
        from hospital.admin.api import kb as kb_module
        called = []
        monkeypatch.setattr(kb_module, "_do_refresh", lambda: (called.append(1) or kb_module.KbStatusResponse(
            ok=True, total_entities=50, by_type={}, schema_errors=0,
            ref_errors=0, contract_errors=0, last_refreshed_at=None,
        )))
        resp = await client.post("/api/v1/admin/kb/refresh", headers=admin_headers)
        assert resp.status_code == 200
        assert called

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, hcp_headers):
        resp = await client.post("/api/v1/admin/kb/refresh", headers=hcp_headers)
        assert resp.status_code == 403


class TestCrawlerNotify:
    @pytest.mark.asyncio
    async def test_valid_signature_triggers_refresh(self, client, monkeypatch):
        from hospital.admin.api import kb as kb_module
        from hospital.config import get_settings
        settings = get_settings()
        original_secret = settings.CRAWLER_WEBHOOK_SECRET
        settings.__dict__["CRAWLER_WEBHOOK_SECRET"] = "test-crawler-secret"

        called = []
        monkeypatch.setattr(kb_module, "_do_refresh", lambda: (called.append(1) or kb_module.KbStatusResponse(
            ok=True, total_entities=42, by_type={}, schema_errors=0,
            ref_errors=0, contract_errors=0, last_refreshed_at=None,
        )))

        body = json.dumps({"event": "kb_updated"}).encode()
        sig = _sign(body)
        resp = await client.post(
            "/api/v1/admin/kb/crawler-notify",
            content=body,
            headers={"X-Crawler-Secret": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert called
        settings.__dict__["CRAWLER_WEBHOOK_SECRET"] = original_secret

    @pytest.mark.asyncio
    async def test_wrong_signature_returns_403(self, client, monkeypatch):
        from hospital.config import get_settings
        settings = get_settings()
        settings.__dict__["CRAWLER_WEBHOOK_SECRET"] = "test-crawler-secret"

        body = b'{"event": "kb_updated"}'
        resp = await client.post(
            "/api/v1/admin/kb/crawler-notify",
            content=body,
            headers={"X-Crawler-Secret": "badbadbadhash", "Content-Type": "application/json"},
        )
        assert resp.status_code == 403
        settings.__dict__["CRAWLER_WEBHOOK_SECRET"] = ""

    @pytest.mark.asyncio
    async def test_unconfigured_secret_returns_503(self, client, monkeypatch):
        from hospital.config import get_settings
        settings = get_settings()
        original = settings.CRAWLER_WEBHOOK_SECRET
        settings.__dict__["CRAWLER_WEBHOOK_SECRET"] = ""

        resp = await client.post(
            "/api/v1/admin/kb/crawler-notify",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 503
        settings.__dict__["CRAWLER_WEBHOOK_SECRET"] = original
