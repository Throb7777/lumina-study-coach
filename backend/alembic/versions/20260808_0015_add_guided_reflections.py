"""Add guided recall and reconstruction reflections.

Revision ID: 20260808_0015
Revises: 20260804_0014
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0015"
down_revision: str | Sequence[str] | None = "20260804_0014"
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
    "material_context",
    "course_completion",
)
NEW_TASKS = (*OLD_TASKS, "recall_questions", "reconstruction_questions")


def task_enum(values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(*values, name="ai_run_task", native_enum=False, create_constraint=True)


def upgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch:
        batch.alter_column(
            "task",
            existing_type=task_enum(OLD_TASKS),
            type_=task_enum(NEW_TASKS),
            existing_nullable=False,
        )
    op.create_table(
        "guided_reflections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "recall",
                "reconstruct",
                name="guided_reflection_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("questions_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("answers_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("reviews_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("question_prompt_text", sa.Text(), server_default="", nullable=False),
        sa.Column("review_prompt_text", sa.Text(), server_default="", nullable=False),
        sa.Column("feedback_text", sa.Text(), server_default="", nullable=False),
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
        sa.ForeignKeyConstraint(["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_record_id", "kind"),
    )
    op.create_index(
        op.f("ix_guided_reflections_daily_record_id"),
        "guided_reflections",
        ["daily_record_id"],
        unique=False,
    )
    # Repair deterministic control-character damage found in historical AI Markdown.
    op.execute(
        "UPDATE daily_records SET context_summary = "
        "replace(context_summary, char(7) || 'omega', '\\omega')"
    )
    op.execute(
        "UPDATE ai_runs SET output_text = "
        "replace(replace(replace(output_text, char(7) || 'omega', '\\omega'), "
        "char(8) || 'inom', '\\binom'), char(12) || 'rac', '\\frac')"
    )
    op.execute(
        "UPDATE ai_runs SET prompt_text = "
        "replace(prompt_text, char(8) || 'inom', '\\binom')"
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_guided_reflections_daily_record_id"),
        table_name="guided_reflections",
    )
    op.drop_table("guided_reflections")
    op.execute(
        "DELETE FROM ai_runs WHERE task IN "
        "('recall_questions', 'reconstruction_questions')"
    )
    with op.batch_alter_table("ai_runs") as batch:
        batch.alter_column(
            "task",
            existing_type=task_enum(NEW_TASKS),
            type_=task_enum(OLD_TASKS),
            existing_nullable=False,
        )
