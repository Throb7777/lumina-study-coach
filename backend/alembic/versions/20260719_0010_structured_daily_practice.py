"""Add six-node daily flow and structured exercise items.

Revision ID: 20260719_0010
Revises: 20260719_0009
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_0010"
down_revision: str | Sequence[str] | None = "20260719_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_NODE_KEYS = (
    "recall",
    "study",
    "reconstruct",
    "practice",
    "review",
    "preview_questions",
    "section_note",
    "daily_complete",
)
NEW_NODE_KEYS = (*OLD_NODE_KEYS, "daily_close")


def node_enum(values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(
        *values,
        name="workflow_node_key",
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    with op.batch_alter_table("workflow_node_states") as batch:
        batch.alter_column(
            "node_key",
            existing_type=node_enum(OLD_NODE_KEYS),
            type_=node_enum(NEW_NODE_KEYS),
            existing_nullable=False,
        )

    op.execute(
        """
        UPDATE workflow_node_states
        SET status = 'completed'
        WHERE node_key = 'preview_questions'
          AND daily_record_id IN (
            SELECT daily_record_id
            FROM workflow_node_states
            WHERE node_key = 'daily_complete' AND status = 'completed'
          )
        """
    )
    op.execute(
        "UPDATE workflow_node_states SET node_key = 'daily_close', position = 6 "
        "WHERE node_key = 'preview_questions'"
    )
    op.execute(
        "DELETE FROM workflow_node_states WHERE node_key IN ('section_note', 'daily_complete')"
    )

    with op.batch_alter_table("exercises") as batch:
        batch.add_column(
            sa.Column("format_version", sa.Integer(), server_default="1", nullable=False)
        )
        batch.add_column(
            sa.Column("status", sa.String(length=30), server_default="draft", nullable=False)
        )

    op.create_table(
        "exercise_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "item_type",
            sa.Enum(
                "single_choice",
                "multiple_choice",
                "short_answer",
                "derivation",
                "proof",
                "calculation",
                "application",
                "extension",
                name="exercise_item_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "difficulty",
            sa.Enum(
                "basic",
                "intermediate",
                "challenge",
                name="exercise_difficulty",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("stem_markdown", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("answer_key_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("rubric_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("source_refs_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("exercise_id", "position"),
    )
    op.create_index("ix_exercise_items_exercise_id", "exercise_items", ["exercise_id"])

    op.create_table(
        "exercise_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_item_id", sa.Integer(), nullable=False),
        sa.Column("answer_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("selected_options_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "unanswered",
                "draft",
                "submitted",
                "graded",
                name="exercise_response_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="unanswered",
            nullable=False,
        ),
        sa.Column("verdict", sa.String(length=30), server_default="", nullable=False),
        sa.Column("feedback_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["exercise_item_id"], ["exercise_items.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("exercise_item_id"),
    )
    op.create_index(
        "ix_exercise_responses_exercise_item_id",
        "exercise_responses",
        ["exercise_item_id"],
    )

    with op.batch_alter_table("mistakes") as batch:
        batch.add_column(sa.Column("exercise_item_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_mistakes_exercise_item_id",
            "exercise_items",
            ["exercise_item_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_mistakes_exercise_item_id", ["exercise_item_id"])


def downgrade() -> None:
    with op.batch_alter_table("mistakes") as batch:
        batch.drop_index("ix_mistakes_exercise_item_id")
        batch.drop_constraint("fk_mistakes_exercise_item_id", type_="foreignkey")
        batch.drop_column("exercise_item_id")

    op.drop_index(
        "ix_exercise_responses_exercise_item_id", table_name="exercise_responses"
    )
    op.drop_table("exercise_responses")
    op.drop_index("ix_exercise_items_exercise_id", table_name="exercise_items")
    op.drop_table("exercise_items")

    with op.batch_alter_table("exercises") as batch:
        batch.drop_column("status")
        batch.drop_column("format_version")

    op.execute(
        "UPDATE workflow_node_states SET node_key = 'preview_questions', position = 6 "
        "WHERE node_key = 'daily_close'"
    )
    op.execute(
        """
        INSERT INTO workflow_node_states (daily_record_id, node_key, position, status)
        SELECT id, 'section_note', 7, 'pending' FROM daily_records
        """
    )
    op.execute(
        """
        INSERT INTO workflow_node_states (daily_record_id, node_key, position, status)
        SELECT id, 'daily_complete', 8,
               CASE WHEN is_completed = 1 THEN 'completed' ELSE 'pending' END
        FROM daily_records
        """
    )
    with op.batch_alter_table("workflow_node_states") as batch:
        batch.alter_column(
            "node_key",
            existing_type=node_enum(NEW_NODE_KEYS),
            type_=node_enum(OLD_NODE_KEYS),
            existing_nullable=False,
        )
