import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from launcher.runtime import (  # noqa: E402
    frontend_build_id,
    health_matches,
    health_matches_frontend,
    open_application,
    runtime_paths,
)


def test_launcher_recognizes_only_the_study_web_health_payload() -> None:
    assert health_matches(
        {
            "status": "ok",
            "service": "learning-flow-coach-api",
            "version": "0.1.2",
        }
    )
    assert not health_matches({"status": "ok", "service": "another-service"})
    assert not health_matches("ok")


def test_launcher_requires_the_expected_ready_frontend_build() -> None:
    payload = {
        "status": "ok",
        "service": "learning-flow-coach-api",
        "version": "0.1.2",
        "frontend_build_id": "current-build",
        "frontend_ready": True,
    }

    assert health_matches_frontend(payload, "current-build")
    assert not health_matches_frontend(payload, "old-build")
    assert not health_matches_frontend({**payload, "frontend_ready": False}, "current-build")


def test_launcher_paths_are_derived_without_a_personal_absolute_path(tmp_path: Path) -> None:
    paths = runtime_paths(tmp_path)

    assert paths.pythonw == tmp_path / "backend" / ".venv" / "Scripts" / "pythonw.exe"
    assert paths.frontend_index == tmp_path / "frontend" / "dist" / "index.html"


def test_launcher_opens_the_course_home_with_build_identity(
    tmp_path: Path, monkeypatch
) -> None:
    paths = runtime_paths(tmp_path)
    paths.frontend_index.parent.mkdir(parents=True)
    paths.frontend_index.write_text("<html>current build</html>", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr("launcher.runtime.os.startfile", opened.append)

    open_application(paths)

    assert opened == [
        f"http://127.0.0.1:8000/courses?launch={frontend_build_id(paths.frontend_index)}"
    ]
