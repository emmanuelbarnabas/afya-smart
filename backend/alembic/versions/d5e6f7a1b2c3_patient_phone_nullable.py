"""Allow patients.phone_number to be NULL (intake patients without a SIM).

Revision ID: d5e6f7a1b2c3
Revises: c4d5e6f7a1b2
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a1b2c3"
down_revision = "c4d5e6f7a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # is_anonymous haikuwahi kuongezwa na migration zilizopita (dev auto-migrate
    # ndiyo ilitengeneza kwenye DB za dev) — DB mpya ya alembic ilikuwa haina
    # hii kwa hivyo intake (mgonjwa bila SIM) ilikuwa inaanguka kwenye INSERT.
    op.add_column(
        "patients",
        sa.Column(
            "is_anonymous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # batch_alter_table kwa ajili ya SQLite (hairekebishi column moja kwa moja)
    # na kwa Postgres hufanya ALTER COLUMN ya kawaida.
    with op.batch_alter_table("patients") as batch_op:
        batch_op.alter_column(
            "phone_number",
            existing_type=sa.String(20),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("patients") as batch_op:
        batch_op.alter_column(
            "phone_number",
            existing_type=sa.String(20),
            nullable=False,
        )
    op.drop_column("patients", "is_anonymous")
