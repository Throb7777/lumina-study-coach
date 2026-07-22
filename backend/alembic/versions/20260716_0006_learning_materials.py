"""Add persistent learning materials.

Revision ID: 20260716_0006
Revises: 20260716_0005
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0006"
down_revision: str | Sequence[str] | None = "20260716_0005"
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
        "learning_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("chapter_id", sa.Integer()),
        sa.Column("section_id", sa.Integer()),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("pdf", "url", name="material_source_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), server_default="", nullable=False),
        sa.Column("original_name", sa.String(length=500), server_default="", nullable=False),
        sa.Column("storage_path", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ready", "failed", name="material_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("error_text", sa.Text(), server_default="", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="0", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_learning_materials_course_id", "learning_materials", ["course_id"])
    op.create_index("ix_learning_materials_chapter_id", "learning_materials", ["chapter_id"])
    op.create_index("ix_learning_materials_section_id", "learning_materials", ["section_id"])
    op.create_index("ix_learning_materials_content_hash", "learning_materials", ["content_hash"])

    op.create_table(
        "material_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=500), server_default="", nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("material_id", "position"),
    )
    op.create_index("ix_material_chunks_material_id", "material_chunks", ["material_id"])

    op.create_table(
        "daily_record_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("range_note", sa.String(length=1000), server_default="", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["daily_record_id"], ["daily_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["material_id"], ["learning_materials.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("daily_record_id", "material_id"),
    )
    op.create_index(
        "ix_daily_record_materials_daily_record_id",
        "daily_record_materials",
        ["daily_record_id"],
    )
    op.create_index(
        "ix_daily_record_materials_material_id",
        "daily_record_materials",
        ["material_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_record_materials_material_id", table_name="daily_record_materials")
    op.drop_index(
        "ix_daily_record_materials_daily_record_id",
        table_name="daily_record_materials",
    )
    op.drop_table("daily_record_materials")
    op.drop_index("ix_material_chunks_material_id", table_name="material_chunks")
    op.drop_table("material_chunks")
    op.drop_index("ix_learning_materials_content_hash", table_name="learning_materials")
    op.drop_index("ix_learning_materials_section_id", table_name="learning_materials")
    op.drop_index("ix_learning_materials_chapter_id", table_name="learning_materials")
    op.drop_index("ix_learning_materials_course_id", table_name="learning_materials")
    op.drop_table("learning_materials")
