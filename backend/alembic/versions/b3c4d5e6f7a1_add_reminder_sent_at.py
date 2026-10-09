"""Add reminder_sent_at to appointments (SMS reminder dedup).

Revision ID: b3c4d5e6f7a1
Revises: a1f2c3d4e5f6
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a1"
down_revision = "a1f2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "reminder_sent_at")
