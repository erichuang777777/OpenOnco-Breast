"""LINE Notify integration.

Sends push messages to HCP mobile phones via LINE Notify API.
Token is stored per-user in the database (users.line_notify_token).

Usage:
    await send_line_notify(token, "王患者：pertuzumab 健保申請截止日明日到期")

LINE Notify API reference: https://notify-bot.line.me/doc/en/
Rate limit: 1,000 messages/hour per token.
"""

from __future__ import annotations

import logging

import httpx

_log = logging.getLogger(__name__)

_LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
_TIMEOUT = 8.0  # seconds


async def send_line_notify(token: str, message: str) -> bool:
    """
    Send a LINE Notify message.

    Returns True on success, False if the token is invalid or rate-limited.
    Never raises — failures are logged and swallowed so the caller's
    primary operation is never blocked by a notification failure.
    """
    if not token or not token.strip():
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _LINE_NOTIFY_URL,
                headers={"Authorization": f"Bearer {token.strip()}"},
                data={"message": f"\n{message}"},
            )
        if resp.status_code == 200:
            return True
        _log.warning("LINE Notify returned %s: %s", resp.status_code, resp.text[:120])
        return False
    except Exception as exc:  # noqa: BLE001
        _log.warning("LINE Notify send failed: %s", exc)
        return False


def format_reminder_message(patient_mrn: str, title: str, urgency: str) -> str:
    """Format a reminder into a concise LINE message."""
    urgency_prefix = {"critical": "🚨 緊急", "high": "⚠️ 重要", "normal": "📋", "low": "ℹ️"}.get(
        urgency, "📋"
    )
    return f"[OpenOnco] {urgency_prefix}\n病患 {patient_mrn}\n{title}"
