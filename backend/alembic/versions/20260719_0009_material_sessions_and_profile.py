"""Add reusable material sessions and course completion summaries.

Revision ID: 20260719_0009
Revises: 20260717_0008
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_0009"
down_revision: str | Sequence[str] | None = "20260717_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_TASKS = (
    "recall_review",
    "reconstruction_review",
    "practice_generation",
    "exercise_grading",
    "preview_questions",
    "section_note_draft",
    "section_note_polish",
    "section_memory",
    "daily_summary",
)
NEW_TASKS = (*OLD_TASKS, "material_context", "course_completion")


def task_enum(values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(*values, name="ai_run_task", native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.add_column("courses", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "courses",
        sa.Column("completion_summary", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "courses",
        sa.Column(
            "completion_summary_version", sa.Integer(), server_default="0", nullable=False
        ),
    )

    op.create_table(
        "material_context_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "preparing",
                "ready",
                "failed",
                name="material_session_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(length=200), server_default="", nullable=False),
        sa.Column(
            "anchor_turn_id", sa.String(length=200), server_default="", nullable=False
        ),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("workspace_path", sa.Text(), nullable=False),
        sa.Column(
            "change_kind", sa.String(length=40), server_default="rebuild", nullable=False
        ),
        sa.Column("error_text", sa.Text(), server_default="", nullable=False),
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
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("section_id", "revision"),
    )
    op.create_index(
        "ix_material_context_sessions_section_id",
        "material_context_sessions",
        ["section_id"],
    )
    op.create_index(
        "ix_material_context_sessions_manifest_hash",
        "material_context_sessions",
        ["manifest_hash"],
    )

    with op.batch_alter_table("ai_runs") as batch:
        batch.alter_column(
            "task",
            existing_type=task_enum(OLD_TASKS),
            type_=task_enum(NEW_TASKS),
            existing_nullable=False,
        )
        batch.add_column(sa.Column("material_context_session_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("material_revision", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "material_manifest_hash",
                sa.String(length=64),
                server_default="",
                nullable=False,
            )
        )
        batch.create_foreign_key(
            "fk_ai_runs_material_context_session_id",
            "material_context_sessions",
            ["material_context_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_ai_runs_material_context_session_id", ["material_context_session_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch:
        batch.drop_index("ix_ai_runs_material_context_session_id")
        batch.drop_constraint("fk_ai_runs_material_context_session_id", type_="foreignkey")
        batch.drop_column("material_manifest_hash")
        batch.drop_column("material_revision")
        batch.drop_column("material_context_session_id")
        batch.alter_column(
            "task",
            existing_type=task_enum(NEW_TASKS),
            type_=task_enum(OLD_TASKS),
            existing_nullable=False,
        )

    op.drop_index(
        "ix_material_context_sessions_manifest_hash",
        table_name="material_context_sessions",
    )
    op.drop_index(
        "ix_material_context_sessions_section_id",
        table_name="material_context_sessions",
    )
    op.drop_table("material_context_sessions")
    op.drop_column("courses", "completion_summary_version")
    op.drop_column("courses", "completion_summary")
    op.drop_column("courses", "completed_at")
