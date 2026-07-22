"""Add AI runs and learning memory.

Revision ID: 20260716_0005
Revises: 20260715_0004
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0005"
down_revision: str | Sequence[str] | None = "20260715_0004"
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
        "course_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("overview", sa.Text(), server_default="", nullable=False),
        sa.Column("core_concepts", sa.Text(), server_default="", nullable=False),
        sa.Column("key_methods", sa.Text(), server_default="", nullable=False),
        sa.Column("unresolved_questions", sa.Text(), server_default="", nullable=False),
        sa.Column("error_patterns", sa.Text(), server_default="", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id"),
    )
    op.create_index("ix_course_memories_course_id", "course_memories", ["course_id"])

    op.create_table(
        "section_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("core_concepts", sa.Text(), server_default="", nullable=False),
        sa.Column("key_methods", sa.Text(), server_default="", nullable=False),
        sa.Column("unresolved_questions", sa.Text(), server_default="", nullable=False),
        sa.Column("error_patterns", sa.Text(), server_default="", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("section_id"),
    )
    op.create_index("ix_section_memories_section_id", "section_memories", ["section_id"])

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "provider",
            sa.Enum("codex", "gemini", name="ai_provider", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "task",
            sa.Enum(
                "recall_review",
                "reconstruction_review",
                "practice_generation",
                "exercise_grading",
                "preview_questions",
                "section_note_draft",
                "section_note_polish",
                "section_memory",
                name="ai_run_task",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("running", "completed", "failed", name="ai_run_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("course_id", sa.Integer()),
        sa.Column("section_id", sa.Integer()),
        sa.Column("daily_record_id", sa.Integer()),
        sa.Column("exercise_id", sa.Integer()),
        sa.Column("model", sa.String(length=100), server_default="", nullable=False),
        sa.Column("thread_id", sa.String(length=200), server_default="", nullable=False),
        sa.Column("context_snapshot", sa.Text(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), server_default="", nullable=False),
        sa.Column("error_text", sa.Text(), server_default="", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["daily_record_id"], ["daily_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_runs_course_id", "ai_runs", ["course_id"])
    op.create_index("ix_ai_runs_section_id", "ai_runs", ["section_id"])
    op.create_index("ix_ai_runs_daily_record_id", "ai_runs", ["daily_record_id"])
    op.create_index("ix_ai_runs_exercise_id", "ai_runs", ["exercise_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_runs_exercise_id", table_name="ai_runs")
    op.drop_index("ix_ai_runs_daily_record_id", table_name="ai_runs")
    op.drop_index("ix_ai_runs_section_id", table_name="ai_runs")
    op.drop_index("ix_ai_runs_course_id", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_index("ix_section_memories_section_id", table_name="section_memories")
    op.drop_table("section_memories")
    op.drop_index("ix_course_memories_course_id", table_name="course_memories")
    op.drop_table("course_memories")
