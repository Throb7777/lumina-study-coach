from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class UninstallMode(str, Enum):
    KEEP_DATA = "KeepData"
    CLEAN_GENERATED = "CleanGenerated"
    CLEAN_ALL = "CleanAll"


GENERATED_RELATIVE_PATHS = (
    Path("backend/.venv"),
    Path("frontend/node_modules"),
    Path("frontend/dist"),
)
RUNTIME_DATA_RELATIVE_PATH = Path("runtime-data")


@dataclass(frozen=True)
class CleanupPlan:
    mode: UninstallMode
    targets: tuple[Path, ...]
    removes_local_data: bool


def build_cleanup_plan(project_root: Path, mode: UninstallMode) -> CleanupPlan:
    root = project_root.resolve()
    targets: tuple[Path, ...] = ()
    if mode in (UninstallMode.CLEAN_GENERATED, UninstallMode.CLEAN_ALL):
        targets += tuple((root / path).resolve() for path in GENERATED_RELATIVE_PATHS)
    if mode is UninstallMode.CLEAN_ALL:
        targets += ((root / RUNTIME_DATA_RELATIVE_PATH).resolve(),)
    _validate_targets(root, targets)
    return CleanupPlan(
        mode=mode,
        targets=targets,
        removes_local_data=mode is UninstallMode.CLEAN_ALL,
    )


def _validate_targets(project_root: Path, targets: tuple[Path, ...]) -> None:
    allowed = {
        *((project_root / path).resolve() for path in GENERATED_RELATIVE_PATHS),
        (project_root / RUNTIME_DATA_RELATIVE_PATH).resolve(),
    }
    if any(target not in allowed or target == project_root for target in targets):
        raise ValueError("cleanup plan contains a path outside the fixed allowlist")


def backup_database(database: Path, destination_dir: Path, now: datetime | None = None) -> Path:
    source = database.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination_root = destination_dir.resolve()
    runtime_data = source.parent.resolve()
    if destination_root == runtime_data or runtime_data in destination_root.parents:
        raise ValueError("backup destination must be outside runtime-data")
    destination_root.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    destination = destination_root / f"learning-flow-coach-{timestamp}.db"
    suffix = 1
    while destination.exists():
        destination = destination_root / f"learning-flow-coach-{timestamp}-{suffix}.db"
        suffix += 1
    with closing(sqlite3.connect(source)) as source_connection:
        with closing(sqlite3.connect(destination)) as destination_connection:
            source_connection.backup(destination_connection)
    return destination


def _plan_payload(plan: CleanupPlan) -> dict[str, object]:
    return {
        "mode": plan.mode.value,
        "targets": [str(path) for path in plan.targets],
        "removes_local_data": plan.removes_local_data,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumina source uninstall helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--root", type=Path, required=True)
    plan_parser.add_argument("--mode", choices=[mode.value for mode in UninstallMode], required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--database", type=Path, required=True)
    backup_parser.add_argument("--destination", type=Path, required=True)

    arguments = parser.parse_args()
    if arguments.command == "plan":
        plan = build_cleanup_plan(arguments.root, UninstallMode(arguments.mode))
        print(json.dumps(_plan_payload(plan), ensure_ascii=False))
        return 0
    destination = backup_database(arguments.database, arguments.destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
