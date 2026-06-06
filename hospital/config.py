"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./hospital.db"

    # ── Knowledge base ────────────────────────────────────────────────────
    KB_ROOT: str = "knowledge_base/hosted/content"

    # ── LLM (extraction only — CHARTER §8.3) ─────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    EXTRACTION_MODEL: str = "claude-sonnet-4-6"

    # ── JWT ───────────────────────────────────────────────────────────────
    JWT_SECRET: str = "dev-secret-CHANGE-IN-PROD"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480          # 8 hours (clinic sessions)
    JWT_ADMIN_EXPIRE_MINUTES: int = 240    # 4 hours (admin sessions)

    # ── Google OAuth ──────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ── Account bootstrap ─────────────────────────────────────────────────
    BOOTSTRAP_ADMIN_EMAIL: str = ""

    # ── Audit ─────────────────────────────────────────────────────────────
    AUDIT_MRN_SALT: str = "dev-salt-CHANGE-IN-PROD"

    # ── Patient plans (gitignored per CHARTER §9.3) ───────────────────────
    PATIENT_PLANS_DIR: str = "patient_plans"

    # ── CORS ─────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    # Comma-separated in env: ALLOWED_ORIGINS=https://app.hospital.tw,https://staging.hospital.tw

    # ── Request size limit ────────────────────────────────────────────────
    MAX_BODY_SIZE_BYTES: int = 1 * 1024 * 1024   # 1 MB default

    # ── Rate limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_LOGIN: str = "20/minute"
    RATE_LIMIT_HIS_WEBHOOK: str = "100/minute"

    # ── HIS adapter (B3) ──────────────────────────────────────────────────
    HIS_WEBHOOK_SECRET: str = ""   # HMAC secret for HIS webhook signature

    # ── KB crawler webhook ────────────────────────────────────────────────────
    CRAWLER_WEBHOOK_SECRET: str = ""  # HMAC-SHA256 secret shared with the KB crawler

    # ── PWA push notifications / VAPID (B7) ───────────────────────────────
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@openonco.local"

    # ── LINE Notify ────────────────────────────────────────────────────────
    LINE_NOTIFY_ENABLED: bool = False  # set True to send LINE messages on high-urgency reminders

    # ── Feature flags — set =false to disable/remove a module ─────────────
    FEATURE_FHIR_IMPORT: bool = True      # POST /fhir/Patient/$import
    FEATURE_TRIALS_SEARCH: bool = True    # GET /trials (CT.gov proxy)
    FEATURE_PDF_EXPORT: bool = True       # GET /plan/{id}/pdf
    FEATURE_LINE_NOTIFY_API: bool = True  # GET|PUT /me/line-notify-token
    FEATURE_CIVIC_LOOKUP: bool = False    # CIViC actionability engine (phase 2 pending)

    @property
    def kb_root_path(self) -> Path:
        return Path(self.KB_ROOT)

    @property
    def patient_plans_path(self) -> Path:
        return Path(self.PATIENT_PLANS_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()
