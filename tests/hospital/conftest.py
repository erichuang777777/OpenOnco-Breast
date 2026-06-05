"""Shared pytest fixtures for hospital package tests."""

from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force SQLite in-memory for all tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod")
os.environ.setdefault("AUDIT_MRN_SALT", "test-salt")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from hospital.db.models import Base, CareTeamMember, Patient
from hospital.db.session import _enable_sqlite_fk, get_db
from hospital.main import app


# ── In-memory DB per test ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    _enable_sqlite_fk(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── FastAPI test client with overridden DB ────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── JWT helpers ───────────────────────────────────────────────────────────────

def make_jwt(
    sub: str = "user-001",
    email: str = "dr@test.com",
    name: str = "Test User",
    role: str = "clinic_hcp",
) -> str:
    from hospital.auth.jwt_utils import create_access_token
    return create_access_token(sub, email, name, role)


@pytest.fixture
def hcp_headers():
    token = make_jwt(role="clinic_hcp")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def board_headers():
    token = make_jwt(role="tumor_board_hcp")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = make_jwt(role="kb_admin", sub="admin-001", email="admin@test.com")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pending_headers():
    token = make_jwt(role="pending")
    return {"Authorization": f"Bearer {token}"}


# ── Patient / care-team seed helpers ─────────────────────────────────────────

@pytest_asyncio.fixture
async def sample_patient(db_session: AsyncSession) -> Patient:
    patient = Patient(
        mrn="MRN-TEST-001",
        masked_name="王●●",
        sex="F",
        dob_year=1975,
        disease_summary="乳癌 HER2+ · 第四期",
        status="active",
        primary_doctor_id="user-001",
        created_by="user-001",
    )
    db_session.add(patient)
    await db_session.flush()
    return patient


@pytest_asyncio.fixture
async def sample_care_team(db_session: AsyncSession, sample_patient: Patient) -> list[CareTeamMember]:
    members = [
        CareTeamMember(
            patient_mrn=sample_patient.mrn,
            user_id="user-001",
            member_role="primary_hcp",
            specialty="Oncology",
            assigned_by="user-001",
        ),
        CareTeamMember(
            patient_mrn=sample_patient.mrn,
            user_id="coord-001",
            member_role="care_coordinator",
            assigned_by="user-001",
        ),
    ]
    db_session.add_all(members)
    await db_session.flush()
    return members
