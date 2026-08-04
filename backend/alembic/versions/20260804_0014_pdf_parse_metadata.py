"""Add PDF parsing metadata to learning materials.

Revision ID: 20260804_0014
Revises: 20260728_0013
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_0014"
down_revision: str | Sequence[str] | None = "20260728_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("learning_materials") as batch:
        batch.add_column(sa.Column("warning_text", sa.Text(), server_default="", nullable=False))
        batch.add_column(sa.Column("total_pages", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("ocr_pages", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(
            sa.Column("failed_pages", sa.Integer(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("learning_materials") as batch:
        batch.drop_column("failed_pages")
        batch.drop_column("ocr_pages")
        batch.drop_column("total_pages")
        batch.drop_column("warning_text")
