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

    @property
    def kb_root_path(self) -> Path:
        return Path(self.KB_ROOT)

    @property
    def patient_plans_path(self) -> Path:
        return Path(self.PATIENT_PLANS_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()
