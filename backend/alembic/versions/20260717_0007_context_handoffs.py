"""Add chapter memory and compact AI context handoffs.

Revision ID: 20260717_0007
Revises: 20260716_0006
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_0007"
down_revision: str | Sequence[str] | None = "20260716_0006"
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
    op.add_column(
        "course_memories",
        sa.Column("generated_outline", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "daily_records",
        sa.Column("context_summary", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "daily_records",
        sa.Column("material_brief", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "daily_records",
        sa.Column(
            "material_context_signature",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
    )
    op.add_column(
        "ai_runs",
        sa.Column("handoff_json", sa.Text(), server_default="", nullable=False),
    )

    op.create_table(
        "chapter_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("core_concepts", sa.Text(), server_default="", nullable=False),
        sa.Column("key_methods", sa.Text(), server_default="", nullable=False),
        sa.Column("unresolved_questions", sa.Text(), server_default="", nullable=False),
        sa.Column("error_patterns", sa.Text(), server_default="", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chapter_id"),
    )
    op.create_index("ix_chapter_memories_chapter_id", "chapter_memories", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_chapter_memories_chapter_id", table_name="chapter_memories")
    op.drop_table("chapter_memories")
    op.drop_column("ai_runs", "handoff_json")
    op.drop_column("daily_records", "material_context_signature")
    op.drop_column("daily_records", "material_brief")
    op.drop_column("daily_records", "context_summary")
    op.drop_column("course_memories", "generated_outline")
