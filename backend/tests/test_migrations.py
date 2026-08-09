from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.migrations import alembic_config, upgrade_database


def test_initial_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_path = (tmp_path / "migration.db").as_posix()
    database_url = f"sqlite+pysqlite:///{database_path}"

    upgrade_database(database_url)
    upgrade_database(database_url)

    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "ai_interactions",
        "ai_runs",
        "app_settings",
        "chapters",
        "chapter_memories",
        "course_memories",
        "courses",
        "daily_record_materials",
        "daily_records",
        "exercises",
        "exercise_items",
        "exercise_response_attachments",
        "exercise_responses",
        "guided_reflections",
        "learning_materials",
        "material_chunks",
        "material_context_sessions",
        "mistakes",
        "preview_question_sets",
        "section_note_prompts",
        "section_memories",
        "sections",
        "workflow_node_states",
    }
    assert {
        "recall_last_learned",
        "study_material_scope",
        "reconstruct_main_learning",
    }.issubset({column["name"] for column in inspect(engine).get_columns("daily_records")})
    assert "note_relative_path" in {
        column["name"] for column in inspect(engine).get_columns("sections")
    }
    assert "reviews_json" in {
        column["name"] for column in inspect(engine).get_columns("guided_reflections")
    }
    engine.dispose()

    command.downgrade(alembic_config(database_url), "base")
    engine = create_engine(database_url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()


def test_guided_reflection_migration_repairs_known_markdown_control_characters(
    tmp_path: Path,
) -> None:
    database_path = (tmp_path / "markdown-repair-migration.db").as_posix()
    database_url = f"sqlite+pysqlite:///{database_path}"
    command.upgrade(alembic_config(database_url), "20260804_0014")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        course_id = connection.execute(
            text("INSERT INTO courses (name) VALUES ('Migration QA') RETURNING id")
        ).scalar_one()
        chapter_id = connection.execute(
            text(
                "INSERT INTO chapters (course_id, title, position) "
                "VALUES (:course_id, 'Chapter', 1) RETURNING id"
            ),
            {"course_id": course_id},
        ).scalar_one()
        section_id = connection.execute(
            text(
                "INSERT INTO sections (chapter_id, title, position, status) "
                "VALUES (:chapter_id, 'Section', 1, 'in_progress') RETURNING id"
            ),
            {"chapter_id": chapter_id},
        ).scalar_one()
        record_id = connection.execute(
            text(
                "INSERT INTO daily_records (section_id, study_date, context_summary) "
                "VALUES (:section_id, '2026-08-08', :summary) RETURNING id"
            ),
            {"section_id": section_id, "summary": "公式 $P(\x07omega)=1$"},
        ).scalar_one()
        run_id = connection.execute(
            text(
                "INSERT INTO ai_runs ("
                "provider, task, status, daily_record_id, context_snapshot, "
                "prompt_text, output_text"
                ") VALUES ("
                "'codex', 'recall_review', 'completed', :record_id, '', :prompt, :output"
                ") RETURNING id"
            ),
            {
                "record_id": record_id,
                "prompt": "组合数 $\x08inom{n}{k}$",
                "output": "分数 $\x0crac{1}{2}$ 与 $P(\x07omega)$",
            },
        ).scalar_one()
    engine.dispose()

    command.upgrade(alembic_config(database_url), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        summary = connection.execute(
            text("SELECT context_summary FROM daily_records WHERE id = :id"),
            {"id": record_id},
        ).scalar_one()
        prompt, output = connection.execute(
            text("SELECT prompt_text, output_text FROM ai_runs WHERE id = :id"),
            {"id": run_id},
        ).one()
    engine.dispose()
    assert summary == r"公式 $P(\omega)=1$"
    assert prompt == r"组合数 $\binom{n}{k}$"
    assert output == r"分数 $\frac{1}{2}$ 与 $P(\omega)$"


def test_note_path_migration_backfills_safe_unique_paths(tmp_path: Path) -> None:
    database_path = (tmp_path / "note-path-migration.db").as_posix()
    database_url = f"sqlite+pysqlite:///{database_path}"
    command.upgrade(alembic_config(database_url), "20260720_0012")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        course_id = connection.execute(
            text(
                """
                INSERT INTO courses (
                    name, description, learning_goal, completion_summary,
                    completion_summary_version
                ) VALUES ('Course: One', '', '', '', 0)
                RETURNING id
                """
            )
        ).scalar_one()
        chapter_id = connection.execute(
            text(
                """
                INSERT INTO chapters (course_id, title, position)
                VALUES (:course_id, 'Chapter: One', 0)
                RETURNING id
                """
            ),
            {"course_id": course_id},
        ).scalar_one()
        for position in range(2):
            connection.execute(
                text(
                    """
                    INSERT INTO sections (chapter_id, title, position, status)
                    VALUES (:chapter_id, 'Topic: One', :position, 'not_started')
                    """
                ),
                {"chapter_id": chapter_id, "position": position},
            )
    engine.dispose()

    command.upgrade(alembic_config(database_url), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        paths = list(
            connection.execute(
                text("SELECT note_relative_path FROM sections ORDER BY id")
            ).scalars()
        )
    engine.dispose()
    assert len(paths) == 2
    assert len({path.casefold() for path in paths}) == 2
    assert all("：" in path and ":" not in path for path in paths)
    assert all("--s" in path for path in paths)
