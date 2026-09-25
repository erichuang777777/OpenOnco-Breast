"""add fhir_patient_id to patients, line_notify_token to users

Revision ID: a1f4e8c2d9b3
Revises: 88bccecba56e
Create Date: 2026-06-06 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1f4e8c2d9b3"
down_revision: Union[str, Sequence[str], None] = "88bccecba56e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("fhir_patient_id", sa.String(), nullable=True),
    )
    op.create_index("ix_patients_fhir_patient_id", "patients", ["fhir_patient_id"])

    op.add_column(
        "users",
        sa.Column("line_notify_token", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_patients_fhir_patient_id", table_name="patients")
    op.drop_column("patients", "fhir_patient_id")
    op.drop_column("users", "line_notify_token")
