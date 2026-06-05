"""VAPID push notification service — Phase B7.

Uses pywebpush when available. Tests patch _send_webpush to avoid real
network calls. If pywebpush is not installed, notify_user() is a no-op
(graceful degradation for environments without the native build tools).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.config import get_settings
from hospital.db.models import PushSubscription

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


async def _send_webpush(
    subscription_info: dict,
    data: str,
    vapid_private_key: str,
    vapid_claims: dict,
) -> int:
    """Send a single push notification. Returns HTTP status code.

    Abstracted so tests can patch this function without network access.
    """
    try:
        from pywebpush import webpush, WebPushException

        webpush(
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
        return 201
    except Exception as exc:
        exc_str = str(exc)
        if "410" in exc_str or "Gone" in exc_str:
            return 410
        log.warning("Push failed: %s", exc_str)
        return 500


async def notify_user(
    db: AsyncSession,
    user_id: str,
    title: str,
    body: str,
) -> None:
    """Send push notification to all active subscriptions of user_id."""
    settings = get_settings()
    if not settings.VAPID_PRIVATE_KEY:
        return

    subs = await db.scalars(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.active.is_(True),
        )
    )

    vapid_claims = {"sub": settings.VAPID_SUBJECT}
    payload = json.dumps({"title": title, "body": body})

    for sub in subs.all():
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh_key,
                "auth": sub.auth_key,
            },
        }
        status = await _send_webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
        )
        if status == 410:
            sub.active = False
            await db.flush()
