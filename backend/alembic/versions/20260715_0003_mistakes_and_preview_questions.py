"""Add structured mistakes and tomorrow preview questions.

Revision ID: 20260715_0003
Revises: 20260714_0002
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0003"
down_revision: str | Sequence[str] | None = "20260714_0002"
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
        "mistakes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("original_question", sa.Text(), nullable=False),
        sa.Column("user_answer", sa.Text(), server_default="", nullable=False),
        sa.Column("error_content", sa.Text(), nullable=False),
        sa.Column(
            "error_type",
            sa.Enum(
                "concept",
                "formula_condition",
                "derivation",
                "calculation",
                "question_understanding",
                "expression",
                "cannot_solve",
                "other",
                name="mistake_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("correct_approach", sa.Text(), nullable=False),
        sa.Column("cause_analysis", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "unresolved",
                "understood",
                name="mistake_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="unresolved",
            nullable=False,
        ),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_mistakes_exercise_id", "mistakes", ["exercise_id"])

    op.create_table(
        "preview_question_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("question_1", sa.Text(), server_default="", nullable=False),
        sa.Column("question_2", sa.Text(), server_default="", nullable=False),
        sa.Column("question_3", sa.Text(), server_default="", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("daily_record_id"),
    )
    op.create_index(
        "ix_preview_question_sets_daily_record_id",
        "preview_question_sets",
        ["daily_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preview_question_sets_daily_record_id",
        table_name="preview_question_sets",
    )
    op.drop_table("preview_question_sets")
    op.drop_index("ix_mistakes_exercise_id", table_name="mistakes")
    op.drop_table("mistakes")
