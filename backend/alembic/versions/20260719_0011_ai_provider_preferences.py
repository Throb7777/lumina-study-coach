"""Track AI model preferences in material sessions and runs.

Revision ID: 20260719_0011
Revises: 20260719_0010
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_0011"
down_revision: str | Sequence[str] | None = "20260719_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("material_context_sessions") as batch:
        batch.add_column(
            sa.Column("model", sa.String(length=100), server_default="", nullable=False)
        )
    with op.batch_alter_table("ai_runs") as batch:
        batch.add_column(
            sa.Column(
                "reasoning_effort",
                sa.String(length=30),
                server_default="",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch:
        batch.drop_column("reasoning_effort")
    with op.batch_alter_table("material_context_sessions") as batch:
        batch.drop_column("model")
