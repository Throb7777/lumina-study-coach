"""Add exercise response attachments.

Revision ID: 20260808_0016
Revises: 20260808_0015
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0016"
down_revision: str | Sequence[str] | None = "20260808_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercise_response_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_response_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=300), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("extracted_text", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=30),
            server_default="ready",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["exercise_response_id"],
            ["exercise_responses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_exercise_response_attachments_exercise_response_id"),
        "exercise_response_attachments",
        ["exercise_response_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_exercise_response_attachments_exercise_response_id"),
        table_name="exercise_response_attachments",
    )
    op.drop_table("exercise_response_attachments")
