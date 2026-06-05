"""Consultations API — Phase B5."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.decision.schemas.consultation import (
    ConsultationCreate,
    ConsultationMessageCreate,
    ConsultationResponse,
)
from hospital.decision.services.consultation_service import (
    add_message,
    close_consultation,
    create_consultation,
    list_consultations_for_patient,
    list_my_consultations,
)

router = APIRouter(tags=["consultations"])


@router.get("/patients/{mrn}/consultations", response_model=list[ConsultationResponse])
async def get_patient_consultations(
    mrn: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[ConsultationResponse]:
    return await list_consultations_for_patient(db, mrn)


@router.post(
    "/patients/{mrn}/consultations",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_patient_consultation(
    mrn: str,
    body: ConsultationCreate,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ConsultationResponse:
    return await create_consultation(db, mrn, body, user["sub"])


@router.get("/consultations", response_model=list[ConsultationResponse])
async def get_my_consultations(
    role: str = "all",
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[ConsultationResponse]:
    return await list_my_consultations(db, user["sub"], role=role)


@router.post(
    "/consultations/{consultation_id}/messages",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    consultation_id: str,
    body: ConsultationMessageCreate,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ConsultationResponse:
    return await add_message(db, consultation_id, body, user["sub"])


@router.patch(
    "/consultations/{consultation_id}/close",
    response_model=ConsultationResponse,
)
async def close_consult(
    consultation_id: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> ConsultationResponse:
    return await close_consultation(db, consultation_id, user["sub"])
