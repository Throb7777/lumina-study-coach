"""Add grounded material versions, citations, video sources, and daily summaries.

Revision ID: 20260717_0008
Revises: 20260717_0007
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_0008"
down_revision: str | Sequence[str] | None = "20260717_0007"
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
)
NEW_TASKS = (*OLD_TASKS, "daily_summary")


def task_enum(values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(*values, name="ai_run_task", native_enum=False, create_constraint=True)


def source_enum(values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(*values, name="material_source_type", native_enum=False, create_constraint=True)


def upgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch:
        batch.alter_column(
            "task",
            existing_type=task_enum(OLD_TASKS),
            type_=task_enum(NEW_TASKS),
            existing_nullable=False,
        )
        batch.add_column(
            sa.Column("source_refs_json", sa.Text(), server_default="", nullable=False)
        )

    with op.batch_alter_table("learning_materials") as batch:
        batch.alter_column(
            "source_type",
            existing_type=source_enum(("pdf", "url")),
            type_=source_enum(("pdf", "url", "video")),
            existing_nullable=False,
        )

    with op.batch_alter_table(
        "material_chunks",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch:
        batch.drop_constraint("uq_material_chunks_material_id", type_="unique")
        batch.add_column(sa.Column("version_hash", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE material_chunks
        SET version_hash = (
            SELECT learning_materials.content_hash
            FROM learning_materials
            WHERE learning_materials.id = material_chunks.material_id
        )
        """
    )
    with op.batch_alter_table("material_chunks") as batch:
        batch.alter_column("version_hash", existing_type=sa.String(length=64), nullable=False)
        batch.create_unique_constraint(
            "uq_material_chunks_material_id_version_hash_position",
            ["material_id", "version_hash", "position"],
        )
        batch.create_index("ix_material_chunks_version_hash", ["version_hash"])

    with op.batch_alter_table("daily_record_materials") as batch:
        batch.add_column(
            sa.Column("content_hash", sa.String(length=64), server_default="", nullable=False)
        )
    op.execute(
        """
        UPDATE daily_record_materials
        SET content_hash = (
            SELECT learning_materials.content_hash
            FROM learning_materials
            WHERE learning_materials.id = daily_record_materials.material_id
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("daily_record_materials") as batch:
        batch.drop_column("content_hash")

    with op.batch_alter_table("material_chunks") as batch:
        batch.drop_index("ix_material_chunks_version_hash")
        batch.drop_constraint(
            "uq_material_chunks_material_id_version_hash_position", type_="unique"
        )
        batch.drop_column("version_hash")
        batch.create_unique_constraint(
            "uq_material_chunks_material_id_position", ["material_id", "position"]
        )

    with op.batch_alter_table("learning_materials") as batch:
        batch.alter_column(
            "source_type",
            existing_type=source_enum(("pdf", "url", "video")),
            type_=source_enum(("pdf", "url")),
            existing_nullable=False,
        )

    with op.batch_alter_table("ai_runs") as batch:
        batch.drop_column("source_refs_json")
        batch.alter_column(
            "task",
            existing_type=task_enum(NEW_TASKS),
            type_=task_enum(OLD_TASKS),
            existing_nullable=False,
        )
