"""Pydantic schemas for user + account management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

VALID_ROLES = Literal[
    "pending", "tumor_board_hcp", "clinic_hcp", "kb_admin", "auditor"
]
ASSIGNABLE_ROLES = Literal[
    "tumor_board_hcp", "clinic_hcp", "kb_admin", "auditor"
]


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    role: str
    active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UserPatch(BaseModel):
    role: Optional[ASSIGNABLE_ROLES] = None
    active: Optional[bool] = None


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class CurrentUserResponse(BaseModel):
    sub: str
    email: str
    name: Optional[str] = None
    role: str
