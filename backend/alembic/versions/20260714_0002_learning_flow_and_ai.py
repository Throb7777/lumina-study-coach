"""Add learning flow content and AI collaboration records.

Revision ID: 20260714_0002
Revises: 20260714_0001
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0002"
down_revision: str | Sequence[str] | None = "20260714_0001"
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
    for column_name in (
        "recall_last_learned",
        "recall_core_concepts",
        "recall_clear_parts",
        "recall_blocked_parts",
        "study_material_scope",
        "reconstruct_problem",
        "reconstruct_main_learning",
        "reconstruct_math",
        "reconstruct_explanation",
    ):
        op.add_column(
            "daily_records",
            sa.Column(column_name, sa.Text(), server_default="", nullable=False),
        )

    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "recall_review",
                "reconstruction_review",
                name="ai_interaction_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("feedback_text", sa.Text(), server_default="", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_ai_interactions_daily_record_id",
        "ai_interactions",
        ["daily_record_id"],
    )
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column("generation_prompt", sa.Text(), nullable=False),
        sa.Column("ai_questions", sa.Text(), server_default="", nullable=False),
        sa.Column("user_answers", sa.Text(), server_default="", nullable=False),
        sa.Column("grading_prompt", sa.Text(), server_default="", nullable=False),
        sa.Column("ai_feedback", sa.Text(), server_default="", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_exercises_daily_record_id", "exercises", ["daily_record_id"])


def downgrade() -> None:
    op.drop_index("ix_exercises_daily_record_id", table_name="exercises")
    op.drop_table("exercises")
    op.drop_index("ix_ai_interactions_daily_record_id", table_name="ai_interactions")
    op.drop_table("ai_interactions")
    for column_name in reversed(
        (
            "recall_last_learned",
            "recall_core_concepts",
            "recall_clear_parts",
            "recall_blocked_parts",
            "study_material_scope",
            "reconstruct_problem",
            "reconstruct_main_learning",
            "reconstruct_math",
            "reconstruct_explanation",
        )
    ):
        op.drop_column("daily_records", column_name)
