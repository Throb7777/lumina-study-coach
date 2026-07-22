from pathlib import Path

from sqlalchemy import create_engine, inspect

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
            "exercise_responses",
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
    engine.dispose()

    command.downgrade(alembic_config(database_url), "base")
    engine = create_engine(database_url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
