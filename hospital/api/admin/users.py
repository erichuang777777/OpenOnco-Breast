"""Admin user management — /api/v1/admin/users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import ADMIN_ROLES, require_role
from hospital.db.models import User
from hospital.db.session import get_db
from hospital.schemas.users import UserListResponse, UserPatch, UserResponse
from hospital.services import audit_service

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=UserListResponse)
async def list_users(
    user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    result = await db.scalars(select(User).order_by(User.created_at))
    users = list(result)
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=len(users),
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserPatch,
    request: Request,
    current_user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    target = await db.scalar(select(User).where(User.user_id == user_id))
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "USER_NOT_FOUND", "message": f"user_id {user_id!r} not found."},
        )
    changes: list[str] = []
    if body.role is not None and body.role != target.role:
        changes.append(f"role: {target.role}→{body.role}")
        target.role = body.role
    if body.active is not None and body.active != target.active:
        changes.append(f"active: {target.active}→{body.active}")
        target.active = body.active

    if changes:
        action = (
            audit_service.USER_DEACTIVATE if body.active is False
            else audit_service.USER_ROLE_CHANGE
        )
        await audit_service.log_action(
            db, user_id=current_user["sub"],
            action=action,
            resource_type="user", resource_id=user_id,
            diff_summary="; ".join(changes),
            ip_address=request.client.host if request.client else None,
        )
    return _user_to_response(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_role(ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete: sets active=False.  Hard delete not allowed (audit trail)."""
    target = await db.scalar(select(User).where(User.user_id == user_id))
    if not target:
        raise HTTPException(status_code=404, detail={"error": "USER_NOT_FOUND"})
    if user_id == current_user["sub"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "SELF_DEACTIVATE", "message": "Cannot deactivate your own account."},
        )
    target.active = False
    await audit_service.log_action(
        db, user_id=current_user["sub"],
        action=audit_service.USER_DEACTIVATE,
        resource_type="user", resource_id=user_id,
        diff_summary="active: True→False (soft delete)",
    )


def _user_to_response(u: User) -> UserResponse:
    return UserResponse(
        user_id=u.user_id,
        email=u.google_email,
        name=u.google_name,
        role=u.role,
        active=u.active,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )
