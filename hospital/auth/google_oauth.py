"""Google OAuth 2.0 flow — redirect + callback handling.

Uses authlib AsyncOAuth2Client for async token exchange.
Google JWKS verification via authlib's built-in OIDC support.

CHARTER §8.3: OAuth flow is identity only — no clinical decisions here.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from jose import jwt as jose_jwt

from hospital.config import get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def build_authorization_url(state: str) -> str:
    """Build the Google consent-screen redirect URL."""
    settings = get_settings()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def generate_state_nonce() -> str:
    return secrets.token_urlsafe(32)


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange auth code for id_token + access_token."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_google_jwks() -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_JWKS_URL)
        resp.raise_for_status()
        return resp.json()


async def verify_id_token(id_token: str) -> dict:
    """Verify Google id_token signature and return claims.

    Returns dict with: sub, email, name, email_verified.
    Raises ValueError if verification fails.
    """
    settings = get_settings()
    try:
        # Decode header to find kid
        unverified = jose_jwt.get_unverified_header(id_token)
        jwks = await get_google_jwks()

        # Find matching key
        key = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == unverified.get("kid")),
            None,
        )
        if not key:
            raise ValueError("No matching JWKS key found for id_token kid.")

        claims = jose_jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
        )
        if not claims.get("email_verified"):
            raise ValueError("Google account email is not verified.")
        return claims

    except Exception as exc:
        raise ValueError(f"id_token verification failed: {exc}") from exc
