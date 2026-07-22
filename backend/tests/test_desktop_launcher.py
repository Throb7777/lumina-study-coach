import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from launcher.runtime import health_matches, open_application, runtime_paths  # noqa: E402


def test_launcher_recognizes_only_the_study_web_health_payload() -> None:
    assert health_matches(
        {
            "status": "ok",
            "service": "learning-flow-coach-api",
            "version": "0.1.0",
        }
    )
    assert not health_matches({"status": "ok", "service": "another-service"})
    assert not health_matches("ok")


def test_launcher_paths_are_derived_without_a_personal_absolute_path(tmp_path: Path) -> None:
    paths = runtime_paths(tmp_path)

    assert paths.pythonw == tmp_path / "backend" / ".venv" / "Scripts" / "pythonw.exe"
    assert paths.frontend_index == tmp_path / "frontend" / "dist" / "index.html"
    assert paths.first_run_marker == tmp_path / "runtime-data" / "first-run.pending"


def test_launcher_opens_first_run_settings_only_while_marker_exists(
    tmp_path: Path, monkeypatch
) -> None:
    paths = runtime_paths(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr("launcher.runtime.os.startfile", opened.append)

    paths.first_run_marker.parent.mkdir(parents=True)
    paths.first_run_marker.write_text("pending", encoding="ascii")
    open_application(paths)
    paths.first_run_marker.unlink()
    open_application(paths)

    assert opened == [
        "http://127.0.0.1:8000/settings?setup=1",
        "http://127.0.0.1:8000/courses",
    ]
