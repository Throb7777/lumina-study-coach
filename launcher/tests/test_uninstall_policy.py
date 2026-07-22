from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from launcher.uninstall_policy import UninstallMode, backup_database, build_cleanup_plan


class CleanupPlanTests(unittest.TestCase):
    def test_keep_data_has_no_cleanup_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = build_cleanup_plan(Path(directory), UninstallMode.KEEP_DATA)

        self.assertEqual(plan.targets, ())
        self.assertFalse(plan.removes_local_data)

    def test_clean_generated_only_contains_fixed_build_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            plan = build_cleanup_plan(root, UninstallMode.CLEAN_GENERATED)

        self.assertEqual(
            plan.targets,
            (
                root / "backend/.venv",
                root / "frontend/node_modules",
                root / "frontend/dist",
            ),
        )
        self.assertNotIn(root / "runtime-data", plan.targets)

    def test_clean_all_adds_runtime_data_but_never_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            plan = build_cleanup_plan(root, UninstallMode.CLEAN_ALL)

        self.assertTrue(plan.removes_local_data)
        self.assertIn(root / "runtime-data", plan.targets)
        self.assertNotIn(root, plan.targets)


class BackupTests(unittest.TestCase):
    def test_backup_is_consistent_and_outside_runtime_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_data = root / "runtime-data"
            runtime_data.mkdir()
            database = runtime_data / "learning-flow-coach.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("create table records (value text)")
                connection.execute("insert into records values ('kept')")
                connection.commit()

            backup = backup_database(
                database,
                root / "backups",
                datetime(2026, 7, 22, 12, 34, 56),
            )

            self.assertEqual(backup.name, "learning-flow-coach-20260722-123456.db")
            with closing(sqlite3.connect(backup)) as connection:
                self.assertEqual(connection.execute("select value from records").fetchone(), ("kept",))

    def test_backup_rejects_destination_inside_runtime_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_data = Path(directory) / "runtime-data"
            runtime_data.mkdir()
            database = runtime_data / "learning-flow-coach.db"
            with closing(sqlite3.connect(database)):
                pass

            with self.assertRaises(ValueError):
                backup_database(database, runtime_data / "backups")


if __name__ == "__main__":
    unittest.main()
