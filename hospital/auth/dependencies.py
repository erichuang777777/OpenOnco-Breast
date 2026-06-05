"""FastAPI dependency functions for authentication + role enforcement."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError

from hospital.auth.jwt_utils import decode_token

COOKIE_NAME = "openonco_session"


def get_token_from_request(request: Request) -> str | None:
    """Prefer HttpOnly cookie; fall back to Authorization header (API clients)."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(request: Request) -> dict:
    """Return decoded JWT payload.  Raises 401 if missing/invalid."""
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHENTICATED", "message": "Login required."},
        )
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHENTICATED", "message": "Invalid or expired token."},
        )
    if payload.get("role") == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "ACCOUNT_PENDING", "message": "Account awaiting role assignment."},
        )
    return payload


def require_role(roles: list[str]):
    """FastAPI dependency factory.  Usage: Depends(require_role(['clinic_hcp']))."""
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_ROLE",
                    "message": f"Required role(s): {roles}. Your role: {user.get('role')}",
                },
            )
        return user
    return _check


# ── Convenience role sets ─────────────────────────────────────────────────────

HCP_ROLES = ["tumor_board_hcp", "clinic_hcp"]
BOARD_ROLES = ["tumor_board_hcp"]
CLINIC_ROLES = ["clinic_hcp"]
ADMIN_ROLES = ["kb_admin"]
AUDIT_ROLES = ["auditor", "kb_admin"]
ALL_CLINICAL = ["tumor_board_hcp", "clinic_hcp", "kb_admin", "auditor"]
