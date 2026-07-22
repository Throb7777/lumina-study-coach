"""Create core learning models.

Revision ID: 20260714_0001
Revises:
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0001"
down_revision: str | Sequence[str] | None = None
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
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("learning_goal", sa.Text(), server_default="", nullable=False),
        *timestamp_columns(),
    )
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chapters_course_id", "chapters", ["course_id"])
    op.create_table(
        "sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "not_started",
                "in_progress",
                "completed",
                name="section_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sections_chapter_id", "sections", ["chapter_id"])
    op.create_table(
        "daily_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("study_date", sa.Date(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), server_default="0", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("section_id", "study_date"),
    )
    op.create_index("ix_daily_records_section_id", "daily_records", ["section_id"])
    op.create_table(
        "workflow_node_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column(
            "node_key",
            sa.Enum(
                "recall",
                "study",
                "reconstruct",
                "practice",
                "review",
                "preview_questions",
                "section_note",
                "daily_complete",
                name="workflow_node_key",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "completed",
                "skipped",
                name="workflow_node_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("daily_record_id", "node_key"),
    )
    op.create_index(
        "ix_workflow_node_states_daily_record_id",
        "workflow_node_states",
        ["daily_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_node_states_daily_record_id", table_name="workflow_node_states")
    op.drop_table("workflow_node_states")
    op.drop_index("ix_daily_records_section_id", table_name="daily_records")
    op.drop_table("daily_records")
    op.drop_index("ix_sections_chapter_id", table_name="sections")
    op.drop_table("sections")
    op.drop_index("ix_chapters_course_id", table_name="chapters")
    op.drop_table("chapters")
    op.drop_table("courses")
