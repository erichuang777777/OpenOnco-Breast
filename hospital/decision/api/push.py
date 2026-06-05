"""Push notification API — Phase B7."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.config import get_settings
from hospital.db.models import PushSubscription
from hospital.db.session import get_db

router = APIRouter(tags=["push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


class UnsubscribeRequest(BaseModel):
    endpoint: str


class SubscriptionResponse(BaseModel):
    id: str
    endpoint: str
    active: bool

    model_config = {"from_attributes": True}


@router.get("/push/vapid-public-key")
async def get_vapid_public_key(
    user: dict = Depends(require_role(HCP_ROLES)),
) -> dict:
    settings = get_settings()
    return {"vapid_public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/push/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    body: SubscribeRequest,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    existing = await db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    if existing:
        existing.active = True
        await db.flush()
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=SubscriptionResponse.model_validate(existing).model_dump(),
        )

    sub = PushSubscription(
        user_id=user["sub"],
        endpoint=body.endpoint,
        p256dh_key=body.p256dh,
        auth_key=body.auth,
        user_agent=body.user_agent,
    )
    db.add(sub)
    await db.flush()
    return SubscriptionResponse.model_validate(sub)


@router.delete("/push/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: UnsubscribeRequest,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> None:
    sub = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.user_id == user["sub"],
        )
    )
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SUBSCRIPTION_NOT_FOUND"},
        )
    await db.delete(sub)
    await db.flush()


@router.get("/push/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[SubscriptionResponse]:
    rows = await db.scalars(
        select(PushSubscription).where(PushSubscription.user_id == user["sub"])
    )
    return [SubscriptionResponse.model_validate(r) for r in rows.all()]
