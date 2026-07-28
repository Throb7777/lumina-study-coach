"""Persist safe and stable Obsidian note paths.

Revision ID: 20260728_0013
Revises: 20260720_0012
Create Date: 2026-07-28
"""

from collections import Counter
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.file_names import safe_path_segment

revision: str = "20260728_0013"
down_revision: str | Sequence[str] | None = "20260720_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEGMENT_MAX_LENGTH = 200


def _base(value: str) -> str:
    return safe_path_segment(value, "_", max_length=SEGMENT_MAX_LENGTH).casefold()


def upgrade() -> None:
    with op.batch_alter_table("sections") as batch:
        batch.add_column(sa.Column("note_relative_path", sa.String(length=1000), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT
                sections.id AS section_id,
                sections.title AS section_title,
                chapters.id AS chapter_id,
                chapters.title AS chapter_title,
                courses.id AS course_id,
                courses.name AS course_name
            FROM sections
            JOIN chapters ON chapters.id = sections.chapter_id
            JOIN courses ON courses.id = chapters.course_id
            ORDER BY sections.id
            """
        )
    ).mappings().all()

    courses = {row["course_id"]: row["course_name"] for row in rows}
    chapters = {
        row["chapter_id"]: (row["course_id"], row["chapter_title"])
        for row in rows
    }
    course_counts = Counter(_base(name) for name in courses.values())
    chapter_counts = Counter(
        (course_id, _base(title)) for course_id, title in chapters.values()
    )
    section_counts = Counter(
        (row["chapter_id"], _base(row["section_title"])) for row in rows
    )
    assigned_paths: set[str] = set()

    for row in rows:
        course_segment = safe_path_segment(
            row["course_name"],
            f"课程-{row['course_id']}",
            max_length=SEGMENT_MAX_LENGTH,
            suffix=f"--c{row['course_id']}",
            force_suffix=course_counts[_base(row["course_name"])] > 1,
        )
        chapter_segment = safe_path_segment(
            row["chapter_title"],
            f"章节-{row['chapter_id']}",
            max_length=SEGMENT_MAX_LENGTH,
            suffix=f"--h{row['chapter_id']}",
            force_suffix=chapter_counts[
                (row["course_id"], _base(row["chapter_title"]))
            ]
            > 1,
        )
        section_segment = safe_path_segment(
            row["section_title"],
            f"小节-{row['section_id']}",
            max_length=SEGMENT_MAX_LENGTH,
            suffix=f"--s{row['section_id']}",
            force_suffix=section_counts[
                (row["chapter_id"], _base(row["section_title"]))
            ]
            > 1,
        )
        relative_path = f"{course_segment}/{chapter_segment}/{section_segment}.md"
        if relative_path.casefold() in assigned_paths:
            section_segment = safe_path_segment(
                row["section_title"],
                f"小节-{row['section_id']}",
                max_length=SEGMENT_MAX_LENGTH,
                suffix=f"--s{row['section_id']}",
                force_suffix=True,
            )
            relative_path = f"{course_segment}/{chapter_segment}/{section_segment}.md"
        assigned_paths.add(relative_path.casefold())
        connection.execute(
            sa.text(
                "UPDATE sections SET note_relative_path = :relative_path WHERE id = :section_id"
            ),
            {
                "relative_path": relative_path,
                "section_id": row["section_id"],
            },
        )

    with op.batch_alter_table("sections") as batch:
        batch.create_unique_constraint(
            "uq_sections_note_relative_path",
            ["note_relative_path"],
        )


def downgrade() -> None:
    with op.batch_alter_table("sections") as batch:
        batch.drop_constraint("uq_sections_note_relative_path", type_="unique")
        batch.drop_column("note_relative_path")
