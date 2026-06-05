"""Patient Registry API — /api/v1/patients."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.session import get_db
from hospital.decision.schemas.patient import (
    CareTeamMemberCreate,
    CareTeamMemberResponse,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
)
from hospital.decision import services as svc_module
from hospital.decision.services import patient_service
from hospital.services import audit_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientResponse])
async def list_patients(
    tab: str = "all",
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[PatientResponse]:
    return await patient_service.list_patients(db, user["sub"], tab=tab)  # type: ignore[arg-type]


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    body: PatientCreate,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    patient = await patient_service.create_patient(db, body, user["sub"])
    await audit_service.log_action(
        db, user_id=user["sub"],
        action=audit_service.PATIENT_CREATE,
        resource_type="patient", resource_id=patient.mrn,
        mrn=patient.mrn,
        ip_address=request.client.host if request.client else None,
    )
    return await patient_service.build_patient_response(db, patient)


@router.get("/{mrn}", response_model=PatientResponse)
async def get_patient(
    mrn: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    patient = await patient_service.get_patient(db, mrn)
    is_own = (
        patient.primary_doctor_id == user["sub"]
        or await patient_service.is_on_care_team(db, mrn, user["sub"])
    )
    if not is_own:
        await audit_service.log_action(
            db, user_id=user["sub"],
            action=audit_service.PATIENT_CROSS_ACCESS,
            resource_type="patient", resource_id=mrn,
            mrn=mrn,
        )
    return await patient_service.build_patient_response(db, patient)


@router.patch("/{mrn}", response_model=PatientResponse)
async def update_patient(
    mrn: str,
    body: PatientUpdate,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    patient = await patient_service.update_patient(db, mrn, body)
    is_own = (
        patient.primary_doctor_id == user["sub"]
        or await patient_service.is_on_care_team(db, mrn, user["sub"])
    )
    if not is_own:
        await audit_service.log_action(
            db, user_id=user["sub"],
            action=audit_service.PATIENT_CROSS_ACCESS,
            resource_type="patient", resource_id=mrn,
            mrn=mrn,
            diff_summary="patch",
        )
    return await patient_service.build_patient_response(db, patient)


@router.get("/{mrn}/care-team", response_model=list[CareTeamMemberResponse])
async def list_care_team(
    mrn: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[CareTeamMemberResponse]:
    members = await patient_service.list_care_team(db, mrn)
    return [CareTeamMemberResponse.model_validate(m) for m in members]


@router.post(
    "/{mrn}/care-team",
    response_model=CareTeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_care_team_member(
    mrn: str,
    body: CareTeamMemberCreate,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CareTeamMemberResponse:
    await patient_service.require_primary_doctor(db, mrn, user["sub"])
    member = await patient_service.add_care_team_member(db, mrn, body, user["sub"])
    await audit_service.log_action(
        db, user_id=user["sub"],
        action=audit_service.CARE_TEAM_ADD,
        resource_type="patient", resource_id=mrn,
        mrn=mrn,
        diff_summary=f"added {body.user_id!r} as {body.member_role}",
    )
    return CareTeamMemberResponse.model_validate(member)


@router.delete("/{mrn}/care-team/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_care_team_member(
    mrn: str,
    target_user_id: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> None:
    await patient_service.require_primary_doctor(db, mrn, user["sub"])
    await patient_service.remove_care_team_member(db, mrn, target_user_id)
    await audit_service.log_action(
        db, user_id=user["sub"],
        action=audit_service.CARE_TEAM_REMOVE,
        resource_type="patient", resource_id=mrn,
        mrn=mrn,
        diff_summary=f"removed {target_user_id!r}",
    )
