"""FastAPI application entry point.

Start:  uvicorn hospital.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from hospital.auth.dependencies import COOKIE_NAME
from hospital.auth.google_oauth import (
    build_authorization_url,
    exchange_code_for_tokens,
    generate_state_nonce,
    verify_id_token,
)
from hospital.auth.jwt_utils import create_access_token
from hospital.config import get_settings
from hospital.db.models import User
from hospital.db.session import create_all_tables, get_db

# ── Sub-routers ───────────────────────────────────────────────────────────────
from hospital.decision.api.plan import router as plan_router
from hospital.decision.api.guidelines import router as guidelines_router
from hospital.decision.api.cases import router as cases_router
from hospital.decision.api.extract import router as extract_router
from hospital.decision.api.patients import router as patients_router
from hospital.decision.api.timeline import router as timeline_router
from hospital.portals.api.his_webhook import router as his_webhook_router
from hospital.decision.api.reminders import router as reminders_router, admin_router as reminders_admin_router
from hospital.decision.api.consultations import router as consultations_router
from hospital.decision.api.mtd import router as mtd_router
from hospital.decision.api.push import router as push_router
from hospital.admin.api.drug_req import router as drug_req_router
from hospital.admin.api.users import router as admin_users_router
from hospital.admin.api.kb import router as admin_kb_router
from hospital.admin.api.clinical_review import router as admin_clinical_review_router
from hospital.admin.api.audit import router as admin_audit_router
from hospital.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (dev / SQLite only; prod uses Alembic migrations)
    settings = get_settings()
    if "sqlite" in settings.DATABASE_URL:
        await create_all_tables()
    # Bootstrap admin account if configured
    await _bootstrap_admin_if_needed()
    yield


app = FastAPI(
    title="OpenOnco Hospital Edition",
    version="0.1.0",
    description="Clinical decision support add-on — breast cancer focus.",
    lifespan=lifespan,
)

settings_instance = get_settings()

# ── Rate limiter (shared instance used by decorated endpoints) ────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[])

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_instance.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-HIS-Secret"],
)


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds MAX_BODY_SIZE_BYTES."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings_instance.MAX_BODY_SIZE_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"error": "PAYLOAD_TOO_LARGE", "message": "Request body exceeds limit."},
            )
        return await call_next(request)


app.add_middleware(_BodySizeLimitMiddleware)

# ── API routes ────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(plan_router,        prefix=API_PREFIX)
app.include_router(guidelines_router,  prefix=API_PREFIX)
app.include_router(cases_router,       prefix=API_PREFIX)
app.include_router(extract_router,     prefix=API_PREFIX)
app.include_router(patients_router,    prefix=API_PREFIX)
app.include_router(timeline_router,    prefix=API_PREFIX)
app.include_router(his_webhook_router,        prefix=API_PREFIX)
app.include_router(reminders_router,          prefix=API_PREFIX)
app.include_router(reminders_admin_router,    prefix=API_PREFIX)
app.include_router(consultations_router,     prefix=API_PREFIX)
app.include_router(mtd_router,               prefix=API_PREFIX)
app.include_router(push_router,              prefix=API_PREFIX)
app.include_router(drug_req_router,    prefix=API_PREFIX)
app.include_router(admin_users_router, prefix=API_PREFIX)
app.include_router(admin_kb_router,    prefix=API_PREFIX)
app.include_router(admin_clinical_review_router, prefix=API_PREFIX)
app.include_router(admin_audit_router, prefix=API_PREFIX)


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/auth/google", tags=["auth"])
@limiter.limit(settings_instance.RATE_LIMIT_LOGIN)
async def google_login(request: Request):
    """Redirect to Google OAuth consent screen."""
    state = generate_state_nonce()
    url = build_authorization_url(state)
    response = RedirectResponse(url=url)
    response.set_cookie("oauth_state", state, httponly=True, samesite="lax", max_age=600)
    return response


@app.get("/auth/google/callback", tags=["auth"])
@limiter.limit(settings_instance.RATE_LIMIT_LOGIN)
async def google_callback(request: Request, code: str, state: str):
    """Handle Google OAuth callback — issue JWT cookie."""
    saved_state = request.cookies.get("oauth_state")
    if not saved_state or saved_state != state:
        return JSONResponse(status_code=400, content={"error": "INVALID_STATE"})

    try:
        tokens = await exchange_code_for_tokens(code)
        claims = await verify_id_token(tokens["id_token"])
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": "AUTH_FAILED", "message": str(exc)})

    google_sub = claims["sub"]
    email = claims.get("email", "")
    name = claims.get("name")

    # Upsert user
    async for db in get_db():
        from sqlalchemy import select as sa_select
        user = await db.scalar(sa_select(User).where(User.google_sub == google_sub))
        if user is None:
            user = User(
                user_id=google_sub,
                google_sub=google_sub,
                google_email=email,
                google_name=name,
                role="pending",
            )
            db.add(user)
        else:
            from datetime import datetime, timezone
            user.last_login_at = datetime.now(timezone.utc)
        break

    settings = get_settings()
    if user.role == "pending":
        response = RedirectResponse(url="/auth/pending")
    else:
        expire = (
            settings.JWT_ADMIN_EXPIRE_MINUTES
            if user.role in ("kb_admin", "auditor")
            else settings.JWT_EXPIRE_MINUTES
        )
        token = create_access_token(
            user.user_id, email, name, user.role, expire_minutes=expire
        )
        home = {
            "tumor_board_hcp": "/board",
            "clinic_hcp": "/clinic",
            "kb_admin": "/admin",
            "auditor": "/admin/audit",
        }.get(user.role, "/")
        response = RedirectResponse(url=home)
        response.set_cookie(
            COOKIE_NAME, token,
            httponly=True, secure=True, samesite="lax",
            max_age=expire * 60,
        )
    response.delete_cookie("oauth_state")
    return response


@app.get("/auth/pending", tags=["auth"])
async def pending_page(request: Request):
    from fastapi.responses import HTMLResponse
    email = request.cookies.get("oauth_state", "")  # best-effort
    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"><title>待開通</title></head>
    <body style="font-family:sans-serif;max-width:600px;margin:4rem auto;text-align:center">
    <h1>帳號已建立</h1>
    <p>您的帳號尚待管理員指派角色。</p>
    <p>請聯絡您的系統管理員並提供您的 Google 帳號 Email。</p>
    <p style="color:#666;font-size:0.9rem">完成後請重新登入。</p>
    <a href="/auth/google">重新登入</a>
    </body></html>
    """)


@app.get("/auth/logout", tags=["auth"])
async def logout():
    response = RedirectResponse(url="/auth/google")
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/auth/me", tags=["auth"])
async def me(request: Request):
    from hospital.auth.dependencies import get_current_user
    user = await get_current_user(request)
    return user


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": app.version}


# ── Bootstrap helper ──────────────────────────────────────────────────────────

async def _bootstrap_admin_if_needed() -> None:
    settings = get_settings()
    if not settings.BOOTSTRAP_ADMIN_EMAIL:
        return
    async for db in get_db():
        from sqlalchemy import select as sa_select, func
        count = await db.scalar(sa_select(func.count()).select_from(User))
        if count == 0:
            admin = User(
                user_id=f"bootstrap-{settings.BOOTSTRAP_ADMIN_EMAIL}",
                google_sub=f"bootstrap-{settings.BOOTSTRAP_ADMIN_EMAIL}",
                google_email=settings.BOOTSTRAP_ADMIN_EMAIL,
                google_name="Bootstrap Admin",
                role="kb_admin",
                active=True,
            )
            db.add(admin)
        break
