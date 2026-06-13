# Security Policy

OpenOnco is a clinical decision **support** resource (not a medical device;
see [`specs/CHARTER.md`](specs/CHARTER.md) §11 + §15). Because it is used in a
clinical context and the Hospital Edition handles protected health
information (PHI), we take security and privacy reports seriously.

## Reporting a vulnerability

**Do not open a public GitHub issue for security or PHI-exposure reports.**

Email the maintainers at **security@openonco.info** with:

- a description of the issue and its impact,
- steps to reproduce (proof-of-concept welcome),
- affected component (`hospital/` backend, `frontend/`, KB engine, or the
  public static site), and version / commit if known.

You can expect:

- acknowledgement within **3 business days**,
- a triage assessment and severity rating within **10 business days**,
- coordinated disclosure once a fix is available. We credit reporters who
  wish to be named.

Please give us a reasonable window to remediate before any public disclosure.

## Scope

In scope:

- `hospital/` FastAPI backend — auth (Google OAuth + JWT), session handling,
  RBAC, audit logging, the HIS webhook (HMAC), and any PHI handling.
- `frontend/` React SPA.
- The knowledge-base engine and validators.

Particularly interested in: authentication/authorization bypass, cross-doctor
PHI access not captured by the audit log, JWT handling, injection, and any
leak of patient data into logs, git history, or public artifacts
(CHARTER §9.3).

Out of scope:

- The correctness of clinical recommendations — those are governed by the
  two-reviewer clinical sign-off process (CHARTER §6.1), not the security
  process. Clinical concerns:
  [open a `clinical-feedback` issue](https://github.com/erichuang777777/OpenOnco-Breast/issues/new?labels=clinical-feedback).
- Denial-of-service via volumetric traffic against a self-hosted instance.

## Operational requirements for deployers

Before exposing a Hospital Edition instance:

- Set strong, unique `JWT_SECRET` and `AUDIT_MRN_SALT` (the defaults are
  `*-CHANGE-IN-PROD` placeholders — the app must not run with them in prod).
- Configure `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` and restrict
  `ALLOWED_ORIGINS` to your real origins.
- Serve only over TLS; set `HIS_WEBHOOK_SECRET` for HIS integration.
- Use PostgreSQL (not the SQLite pilot default) and enable at-rest encryption
  for `plans.plan_json` (PHI).
- Never commit `.env` or any patient artifact (see `.gitignore` + CHARTER §9.3).
