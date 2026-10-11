"""Add services + contact to facilities (USSD \"Tafuta hospitali\": huduma na mawasiliano).

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a1b2c3
Create Date: 2026-10-11
"""
from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d5e6f7a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("facilities", sa.Column("services", sa.String(length=500), nullable=True))
    op.add_column("facilities", sa.Column("contact", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("facilities", "contact")
    op.drop_column("facilities", "services")
