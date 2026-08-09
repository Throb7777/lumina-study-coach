from __future__ import annotations

import json
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from launcher.data_archive import create_backup_archive
from launcher.release_entry import (
    apply_install_config,
    configure_release_environment,
    frontend_build_id,
    health_matches_frontend,
    initialize_data_root,
    open_application,
    release_data_root,
    release_paths,
    release_port,
    run_server,
    stop_service,
    wait_until_stopped,
)


def create_record_database(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("create table records (value text)")
        connection.execute("insert into records values (?)", (value,))
        connection.commit()


def test_release_data_root_prefers_explicit_override(tmp_path: Path) -> None:
    environment = {
        "LUMINA_DATA_DIR": str(tmp_path / "qa-data"),
        "LOCALAPPDATA": str(tmp_path / "local"),
    }

    assert release_data_root(environment) == (tmp_path / "qa-data").resolve()


def test_release_data_root_uses_local_app_data(tmp_path: Path) -> None:
    assert release_data_root({"LOCALAPPDATA": str(tmp_path)}) == (tmp_path / "Lumina").resolve()


def test_release_data_root_does_not_inherit_when_empty_environment_is_explicit() -> None:
    assert release_data_root({}) == (Path.home() / ".local" / "share" / "Lumina").resolve()


def test_release_port_rejects_invalid_values() -> None:
    assert release_port({"LEARNING_COACH_PORT": "8123"}) == 8123
    assert release_port({"LEARNING_COACH_PORT": "invalid"}) == 8000
    assert release_port({"LEARNING_COACH_PORT": "70000"}) == 8000
    assert release_port({}) == 8000


def test_install_config_sets_defaults_without_overriding_environment(tmp_path: Path) -> None:
    executable = tmp_path / "app" / "Lumina.exe"
    executable.parent.mkdir()
    executable.parent.joinpath("install-config.json").write_text(
        '{"data_dir":"C:\\\\Lumina QA","port":8124}',
        encoding="utf-8",
    )
    environment = {"LEARNING_COACH_PORT": "8125"}

    apply_install_config(environment, executable)

    assert environment["LUMINA_DATA_DIR"] == r"C:\Lumina QA"
    assert environment["LEARNING_COACH_PORT"] == "8125"


def test_install_config_accepts_windows_utf8_bom(tmp_path: Path) -> None:
    executable = tmp_path / "app" / "Lumina.exe"
    executable.parent.mkdir()
    executable.parent.joinpath("install-config.json").write_text(
        '{"data_dir":"C:\\\\Lumina QA","port":8124}',
        encoding="utf-8-sig",
    )
    environment: dict[str, str] = {}

    apply_install_config(environment, executable)

    assert environment == {
        "LUMINA_DATA_DIR": r"C:\Lumina QA",
        "LEARNING_COACH_PORT": "8124",
    }


def test_release_environment_uses_separate_data_and_bundle_roots(tmp_path: Path) -> None:
    environment = {
        "LUMINA_DATA_DIR": str(tmp_path / "data"),
        "LEARNING_COACH_PORT": "8123",
    }
    paths = release_paths(
        environment,
        executable=tmp_path / "app" / "Lumina.exe",
        bundled=tmp_path / "bundle",
    )

    configure_release_environment(paths, environment)

    assert environment["LEARNING_COACH_HOST"] == "127.0.0.1"
    assert environment["LEARNING_COACH_PORT"] == "8123"
    assert environment["LEARNING_COACH_STATIC_DIR"] == str(
        (tmp_path / "bundle" / "frontend" / "dist").resolve()
    )
    assert environment["LEARNING_COACH_RUNTIME_DATA_DIR"] == str(
        (tmp_path / "data").resolve()
    )
    assert environment["LEARNING_COACH_DATABASE_PATH"] == str(
        (tmp_path / "data" / "learning-flow-coach.db").resolve()
    )
    assert environment["LEARNING_COACH_AI_RUNTIME_DIR"] == str(
        (tmp_path / "data" / "ai").resolve()
    )


def test_first_run_marker_is_created_only_without_a_database() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        environment = {"LUMINA_DATA_DIR": str(root / "new")}
        paths = release_paths(
            environment,
            executable=root / "Lumina.exe",
            bundled=root / "bundle",
        )

        initialize_data_root(paths)
        assert paths.first_run_marker.read_text(encoding="ascii") == "pending"

        paths.first_run_marker.unlink()
        paths.database.touch()
        initialize_data_root(paths)
        assert not paths.first_run_marker.exists()


def test_release_launcher_requires_the_expected_ready_frontend_build() -> None:
    payload = {
        "status": "ok",
        "service": "learning-flow-coach-api",
        "frontend_build_id": "current-build",
        "frontend_ready": True,
    }

    assert health_matches_frontend(payload, "current-build")
    assert not health_matches_frontend(payload, "old-build")
    assert not health_matches_frontend({**payload, "frontend_ready": False}, "current-build")


def test_release_launcher_opens_courses_with_build_identity(
    tmp_path: Path, monkeypatch
) -> None:
    paths = release_paths(
        {"LUMINA_DATA_DIR": str(tmp_path / "data")},
        executable=tmp_path / "Lumina.exe",
        bundled=tmp_path / "bundle",
    )
    index_file = paths.static_dir / "index.html"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("<html>release build</html>", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr("launcher.release_entry.os.startfile", opened.append)

    open_application(paths, {"LEARNING_COACH_PORT": "8123"})

    assert opened == [
        f"http://127.0.0.1:8123/courses?launch={frontend_build_id(index_file)}"
    ]


def test_wait_until_stopped_waits_for_health_and_port_release(monkeypatch) -> None:
    health_states = iter((True, False, False))
    port_states = iter((True, False))
    monkeypatch.setattr(
        "launcher.release_entry.service_is_ready",
        lambda *_args, **_kwargs: next(health_states),
    )
    monkeypatch.setattr(
        "launcher.release_entry.port_is_in_use",
        lambda *_args, **_kwargs: next(port_states),
    )
    monkeypatch.setattr("launcher.release_entry.time.sleep", lambda _seconds: None)

    assert wait_until_stopped({}, timeout=1)


def test_stop_service_waits_after_shutdown_request(monkeypatch) -> None:
    waited = []
    monkeypatch.setattr("launcher.release_entry.service_is_ready", lambda *_args: True)
    monkeypatch.setattr("launcher.release_entry.service_process_id", lambda *_args: 2468)
    monkeypatch.setattr("launcher.release_entry.request_shutdown", lambda *_args: True)
    monkeypatch.setattr(
        "launcher.release_entry.wait_until_stopped",
        lambda *_args, **kwargs: waited.append(kwargs.get("process_id")) or True,
    )

    assert stop_service({}, silent=True) == 0
    assert waited == [2468]


def test_stop_service_fails_when_process_does_not_exit(monkeypatch) -> None:
    monkeypatch.setattr("launcher.release_entry.service_is_ready", lambda *_args: True)
    monkeypatch.setattr("launcher.release_entry.service_process_id", lambda *_args: 2468)
    monkeypatch.setattr("launcher.release_entry.request_shutdown", lambda *_args: True)
    monkeypatch.setattr(
        "launcher.release_entry.wait_until_stopped",
        lambda *_args, **_kwargs: False,
    )

    assert stop_service({}, silent=True) == 1


def test_stop_service_ignores_unrelated_port_when_lumina_is_not_running(
    monkeypatch,
) -> None:
    monkeypatch.setattr("launcher.release_entry.service_is_ready", lambda *_args: False)
    monkeypatch.setattr("launcher.release_entry.service_process_id", lambda *_args: None)
    monkeypatch.setattr("launcher.release_entry.port_is_in_use", lambda *_args: True)

    assert stop_service({}, silent=True) == 0


def test_run_server_applies_pending_restore_and_starts_replacement_service(
    tmp_path: Path,
    monkeypatch,
) -> None:
    environment = {"LUMINA_DATA_DIR": str(tmp_path / "runtime")}
    paths = release_paths(
        environment,
        executable=tmp_path / "Lumina.exe",
        bundled=tmp_path / "bundle",
    )
    create_record_database(paths.database, "current")
    source_database = tmp_path / "source" / "learning-flow-coach.db"
    create_record_database(source_database, "restored")
    source_materials = source_database.parent / "materials"
    source_materials.mkdir()
    source_materials.joinpath("lesson.txt").write_text("portable", encoding="utf-8")
    archive = create_backup_archive(
        source_database,
        source_materials,
        tmp_path / "source-backups",
        datetime(2026, 8, 8, 12, 0, 0),
    )
    assert archive is not None
    staging = paths.data_root / "restore-staging"
    staging.mkdir(parents=True)
    staged_archive = staging / ("a" * 32 + ".zip")
    archive.replace(staged_archive)
    paths.data_root.joinpath("restore.pending.json").write_text(
        json.dumps(
            {
                "token": "a" * 32,
                "archive": str(staged_archive),
                "obsidian_vault_path": "",
            }
        ),
        encoding="utf-8",
    )
    starts: list[tuple[object, dict[str, str]]] = []
    monkeypatch.setattr("app.desktop_server.run", lambda: None)
    monkeypatch.setattr(
        "launcher.release_entry.start_service",
        lambda actual_paths, actual_environment: starts.append(
            (actual_paths, actual_environment)
        ),
    )

    assert run_server(paths, environment) == 0

    with closing(sqlite3.connect(paths.database)) as connection:
        assert connection.execute("select value from records").fetchone() == ("restored",)
    assert paths.materials.joinpath("lesson.txt").read_text(encoding="utf-8") == "portable"
    assert not staged_archive.exists()
    assert not paths.data_root.joinpath("restore.pending.json").exists()
    result = json.loads(
        paths.data_root.joinpath("restore-results", "a" * 32 + ".json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == "completed"
    assert Path(result["safety_backup"]).is_file()
    assert starts == [(paths, environment)]


def test_installer_uses_named_install_and_uninstall_components() -> None:
    root = Path(__file__).resolve().parents[2]
    installer = root.joinpath("installer", "Lumina.iss").read_text(encoding="utf-8")

    assert 'MyOutputBase "install_Lumina-"' in installer
    assert "UninstallFilesDir={app}\\uninstall_Lumina" in installer
    assert "UninstallDisplayName={#MyAppName}" in installer
