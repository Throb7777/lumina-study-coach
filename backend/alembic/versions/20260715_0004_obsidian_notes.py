"""Add local settings and section note prompts.

Revision ID: 20260715_0004
Revises: 20260715_0003
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0004"
down_revision: str | Sequence[str] | None = "20260715_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        *timestamp_columns(),
    )
    op.create_table(
        "section_note_prompts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("daily_record_id"),
    )
    op.create_index(
        "ix_section_note_prompts_daily_record_id",
        "section_note_prompts",
        ["daily_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_section_note_prompts_daily_record_id",
        table_name="section_note_prompts",
    )
    op.drop_table("section_note_prompts")
    op.drop_table("app_settings")
