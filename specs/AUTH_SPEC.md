# Authentication & Account Management Specification

**Version:** 0.1 draft  
**Status:** pending review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Overview

Authentication uses **Google OAuth 2.0** (Sign In with Google).  
Google proves identity; the **OpenOnco system assigns roles**.

No domain restriction — any Google account can attempt sign-in.  
Without an assigned role the user sees a "waiting for activation" screen.

Patient authentication is **out of scope for v1** — patients access plans
via signed URL tokens (see `PORTAL_SPEC.md §4`).

---

## 2  Sign-in flow

```
Browser                    FastAPI                   Google OAuth
   │                          │                           │
   │── GET /auth/google ──────►│                           │
   │                          │── redirect ───────────────►│
   │                          │   (state=nonce, scope=     │
   │                          │    openid email profile)   │
   │◄── 302 ─────────────────-│                           │
   │                          │                           │
   │── GET /auth/google/callback?code=... ────────────────►│
   │                          │◄── id_token + access_token─│
   │                          │                           │
   │                          │  verify id_token
   │                          │  extract sub, email, name
   │                          │
   │                          │  lookup users WHERE google_sub = sub
   │                          │
   │                          │  ┌─ NOT FOUND ──────────────────────────┐
   │                          │  │  INSERT user (pending role)           │
   │                          │  │  redirect → /auth/pending             │
   │                          │  └──────────────────────────────────────┘
   │                          │
   │                          │  ┌─ FOUND, role=pending ────────────────┐
   │                          │  │  redirect → /auth/pending             │
   │                          │  └──────────────────────────────────────┘
   │                          │
   │                          │  ┌─ FOUND, active role ─────────────────┐
   │                          │  │  issue JWT (sub, email, role, exp)    │
   │                          │  │  set HttpOnly cookie OR return token  │
   │                          │  │  redirect → / (role-appropriate home) │
   │                          │  └──────────────────────────────────────┘
   │◄── JWT cookie / redirect ─│
```

---

## 3  JWT claims

```json
{
  "sub":   "google-sub-12345",
  "email": "dr.wang@example.com",
  "name":  "王大明",
  "role":  "tumor_board_hcp",
  "iat":   1748923380,
  "exp":   1748952180
}
```

| Claim | Value | Notes |
|-------|-------|-------|
| `sub` | Google `sub` from id_token | Stable unique identifier |
| `email` | Google email | Display only; not used as key |
| `name` | Google display name | Display only |
| `role` | Assigned in OpenOnco DB | See role table in §4 |
| `exp` | `iat` + 8 hours | Clinic sessions; /admin = 4 hours |

Token delivery: **HttpOnly Secure cookie** (`openonco_session`).  
Token size is small enough for cookie; no localStorage.

---

## 4  Role model

| Role | Chinese | Default home | Can be self-assigned |
|------|---------|-------------|----------------------|
| `pending` | 待開通 | /auth/pending | — |
| `tumor_board_hcp` | 腫瘤科/MDT 醫師 | /board | No |
| `clinic_hcp` | 門診醫師 | /clinic | No |
| `kb_admin` | 知識庫管理員 | /admin/kb | No |
| `auditor` | 臨床稽核員 | /admin/audit | No |

All role assignments are made by a user with `kb_admin` role via
`/admin/users`.  First `kb_admin` must be bootstrapped via environment
variable (see §7).

---

## 5  Auth endpoints

### `GET /auth/google`
Redirects to Google OAuth consent screen.  
Sets a `state` nonce cookie (HttpOnly, SameSite=Lax, 10min TTL) to
prevent CSRF.

### `GET /auth/google/callback`
Handles Google redirect.  
Validates `state` nonce.  Exchanges `code` for tokens.  
Verifies `id_token` signature against Google's public keys (JWKS URI).  
Creates or looks up user.  Issues JWT cookie.

### `GET /auth/me`
Returns current user info from JWT.  
**Required:** any authenticated role.

```json
{"sub": "...", "email": "...", "name": "...", "role": "clinic_hcp"}
```

### `POST /auth/logout`
Clears the `openonco_session` cookie.  Returns `{"status": "logged_out"}`.

### `GET /auth/pending`
Rendered HTML page: "您的帳號已建立，請聯絡管理員開通。"  
Shows email address so admin can identify the request.

---

## 6  Account management endpoints

All require `role=kb_admin`.

### `GET /api/v1/admin/users`

List all users.

**Response:**
```json
{
  "users": [
    {
      "user_id": "google-sub-12345",
      "email": "dr.wang@example.com",
      "name": "王大明",
      "role": "tumor_board_hcp",
      "active": true,
      "created_at": "2026-06-01T10:00:00Z",
      "last_login_at": "2026-06-03T07:23:00Z"
    }
  ]
}
```

---

### `PATCH /api/v1/admin/users/{user_id}`

Update role or active status.

```json
{"role": "clinic_hcp", "active": true}
```

`role` must be one of the valid roles (not `pending`).  
Setting `active: false` immediately invalidates issued JWTs
(checked against DB on each request if `active` flag is consulted).

---

### `DELETE /api/v1/admin/users/{user_id}`

Soft-delete: sets `active=false`.  
Hard delete not allowed — preserves audit trail linkage.

---

## 7  First-run bootstrap

The first `kb_admin` is seeded via environment variable:

```ini
BOOTSTRAP_ADMIN_EMAIL=admin@hospital.org.tw
```

On startup, if `users` table is empty and `BOOTSTRAP_ADMIN_EMAIL` is set,
insert a user row with that email + `role=kb_admin` + `active=true`.  
On first Google sign-in with that email, the account is activated.

---

## 8  Database additions

Add to the `users` table (update from `DATABASE_SCHEMA_SPEC.md`):

```sql
ALTER TABLE users
  ADD COLUMN google_sub       TEXT UNIQUE,       -- Google subject ID
  ADD COLUMN google_email     TEXT,
  ADD COLUMN google_name      TEXT,
  ADD COLUMN auth_provider    TEXT NOT NULL DEFAULT 'google'
                              CHECK (auth_provider IN ('google', 'local')),
  ADD COLUMN last_login_at    TIMESTAMPTZ;

-- Remove NOT NULL constraint on password_hash for Google-auth users:
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
```

Full updated users table:

```sql
CREATE TABLE users (
    user_id         TEXT PRIMARY KEY,        -- = Google sub
    google_sub      TEXT UNIQUE NOT NULL,
    google_email    TEXT NOT NULL,
    google_name     TEXT,
    role            TEXT NOT NULL DEFAULT 'pending'
                    CHECK (role IN (
                        'pending','tumor_board_hcp','clinic_hcp',
                        'kb_admin','auditor'
                    )),
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    auth_provider   TEXT NOT NULL DEFAULT 'google',
    password_hash   TEXT,                    -- NULL for Google-auth users
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);
```

---

## 9  FastAPI middleware

```python
from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("openonco_session")
    if not token:
        raise HTTPException(401, "UNAUTHENTICATED")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "UNAUTHENTICATED")
    if payload.get("role") == "pending":
        raise HTTPException(403, "ACCOUNT_PENDING")
    return payload

def require_role(roles: list[str]):
    async def _check(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "INSUFFICIENT_ROLE")
        return user
    return _check
```

Usage:
```python
@router.post("/plan")
async def generate(
    body: PlanRequest,
    user = Depends(require_role(["tumor_board_hcp", "clinic_hcp"]))
):
    ...
```

---

## 10  Environment variables

```ini
GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
GOOGLE_REDIRECT_URI=https://onco.hospital.org.tw/auth/google/callback

JWT_SECRET=<32-byte random hex>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

BOOTSTRAP_ADMIN_EMAIL=admin@hospital.org.tw
```

---

## 11  Dependencies

```toml
# pyproject.toml additions
authlib = ">=1.3"        # Google OAuth 2.0 + JWKS verification
python-jose = {extras = ["cryptography"], version = ">=3.3"}
httpx = ">=0.27"         # async HTTP for token exchange
itsdangerous = ">=2.2"   # state nonce signing
```

---

## 12  Security notes

| Risk | Mitigation |
|------|-----------|
| CSRF on callback | `state` nonce in HttpOnly cookie; validated on callback |
| JWT tampering | Signed with `JWT_SECRET`; verified on every request |
| Account enumeration | `/auth/pending` shows only own email, not existence of others |
| Privilege escalation | Role change requires `kb_admin`; logged in `audit_log` |
| Inactive user token reuse | `active` flag checked on sensitive endpoints (plan write, admin) |
| Google token replay | `nonce` in id_token validated; `iat` checked against clock skew |
