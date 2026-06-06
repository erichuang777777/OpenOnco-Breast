"""Development-only local login — POST /auth/dev/login

Enabled only when DEV_LOCAL_LOGIN=true AND DATABASE_URL contains 'sqlite'.
Allows instant token issuance for any email/role without Google OAuth,
so developers can test all roles without OAuth credentials.

NEVER enable in production.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from hospital.auth.jwt_utils import create_access_token
from hospital.config import get_settings
from hospital.db.models import User
from hospital.db.session import db_context

router = APIRouter(prefix="/auth/dev", tags=["dev-auth"])

VALID_ROLES = ["clinic_hcp", "tumor_board_hcp", "kb_admin", "auditor"]


class DevLoginRequest(BaseModel):
    email: str
    role: str = "clinic_hcp"


@router.post("/login")
async def dev_login(body: DevLoginRequest) -> JSONResponse:
    """Issue a JWT for the given email+role without OAuth. Dev only."""
    settings = get_settings()

    # Hard guard: refuse if not SQLite or flag not set
    if not settings.DEV_LOCAL_LOGIN or "sqlite" not in settings.DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "DEV_LOGIN_DISABLED", "message": "Dev login is only available in local SQLite mode."},
        )

    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_ROLE", "message": f"role must be one of {VALID_ROLES}"},
        )

    user_id = f"dev-{body.email}"
    async with db_context() as db:
        user = await db.scalar(select(User).where(User.google_email == body.email))
        if user is None:
            user = User(
                user_id=user_id,
                google_sub=user_id,
                google_email=body.email,
                google_name=body.email.split("@")[0],
                role=body.role,
                active=True,
            )
            db.add(user)
        else:
            user.role = body.role
            user.active = True
            user.last_login_at = datetime.now(timezone.utc)

    expire = (
        settings.JWT_ADMIN_EXPIRE_MINUTES
        if body.role in ("kb_admin", "auditor")
        else settings.JWT_EXPIRE_MINUTES
    )
    token = create_access_token(
        user.user_id, body.email, user.google_name, body.role,
        expire_minutes=expire,
    )

    from hospital.auth.dependencies import COOKIE_NAME
    response = JSONResponse({"ok": True, "role": body.role, "email": body.email})
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, secure=False, samesite="lax",
        max_age=expire * 60,
    )
    return response


@router.get("/users")
async def dev_list_users() -> list[dict]:
    """List all local users (dev only)."""
    settings = get_settings()
    if not settings.DEV_LOCAL_LOGIN or "sqlite" not in settings.DATABASE_URL:
        raise HTTPException(status_code=403, detail={"error": "DEV_LOGIN_DISABLED"})

    async with db_context() as db:
        users = list(await db.scalars(select(User).order_by(User.created_at)))
    return [
        {"user_id": u.user_id, "email": u.google_email, "role": u.role, "active": u.active}
        for u in users
    ]
