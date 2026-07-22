"""Separate active material revisions from refresh attempts.

Revision ID: 20260720_0012
Revises: 20260719_0011
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0012"
down_revision: str | Sequence[str] | None = "20260719_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("learning_materials") as batch:
        batch.add_column(
            sa.Column("source_hash", sa.String(length=64), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "parser_version",
                sa.String(length=60),
                server_default="legacy-v1",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "last_refresh_status",
                sa.Enum(
                    "idle",
                    "running",
                    "succeeded",
                    "failed",
                    name="material_refresh_status",
                    native_enum=False,
                ),
                server_default="idle",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("last_refresh_error", sa.Text(), server_default="", nullable=False)
        )
        batch.add_column(sa.Column("last_refresh_at", sa.DateTime()))
        batch.add_column(sa.Column("last_success_at", sa.DateTime()))
        batch.create_index("ix_learning_materials_source_hash", ["source_hash"])

    op.execute("UPDATE learning_materials SET source_hash = content_hash")
    op.execute(
        "UPDATE learning_materials SET last_refresh_status = "
        "CASE WHEN status = 'ready' THEN 'succeeded' ELSE 'failed' END, "
        "last_refresh_error = CASE WHEN status = 'failed' THEN error_text ELSE '' END, "
        "last_success_at = CASE WHEN status = 'ready' THEN updated_at ELSE NULL END"
    )


def downgrade() -> None:
    with op.batch_alter_table("learning_materials") as batch:
        batch.drop_index("ix_learning_materials_source_hash")
        batch.drop_column("last_success_at")
        batch.drop_column("last_refresh_at")
        batch.drop_column("last_refresh_error")
        batch.drop_column("last_refresh_status")
        batch.drop_column("parser_version")
        batch.drop_column("source_hash")
