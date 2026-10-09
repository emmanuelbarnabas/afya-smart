"""Add clinician_urgency to queue_entries (front-desk feedback loop).

Revision ID: c4d5e6f7a1b2
Revises: b3c4d5e6f7a1
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7a1b2"
down_revision = "b3c4d5e6f7a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("queue_entries", sa.Column("clinician_urgency", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("queue_entries", "clinician_urgency")
