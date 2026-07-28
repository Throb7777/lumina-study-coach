from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import AiProvider, AiRun, AiRunStatus, AiRunTask


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "learning-flow-coach-api",
        "version": "0.1.2",
    }


def test_terminal_service_cannot_be_shutdown_from_web(client: TestClient) -> None:
    response = client.post("/api/system/shutdown", json={"confirm": True})

    assert response.status_code == 409
    assert "启动终端" in response.json()["detail"]


def test_desktop_service_accepts_same_origin_shutdown(
    tmp_path: Path, database_url: str
) -> None:
    shutdown_requested = Event()
    application = create_app(
        tmp_path / "missing-dist",
        database_url=database_url,
        material_dir=tmp_path / "materials",
        shutdown_callback=shutdown_requested.set,
        first_run_marker=tmp_path / "first-run.pending",
    )

    with TestClient(application) as desktop_client:
        response = desktop_client.post(
            "/api/system/shutdown",
            json={"confirm": True},
            headers={"origin": "http://testserver"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "stopping"}
        assert shutdown_requested.wait(1)


def test_desktop_service_rejects_cross_site_shutdown(
    tmp_path: Path, database_url: str
) -> None:
    application = create_app(
        tmp_path / "missing-dist",
        database_url=database_url,
        material_dir=tmp_path / "materials",
        shutdown_callback=lambda: None,
        first_run_marker=tmp_path / "first-run.pending",
    )

    with TestClient(application) as desktop_client:
        response = desktop_client.post(
            "/api/system/shutdown",
            json={"confirm": True},
            headers={"origin": "https://example.com", "sec-fetch-site": "cross-site"},
        )

        assert response.status_code == 403


def test_cross_site_browser_write_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/onboarding/complete",
        headers={
            "Origin": "https://malicious.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "拒绝跨站写入请求。"


def test_same_origin_browser_write_is_allowed(client: TestClient) -> None:
    response = client.post(
        "/api/onboarding/complete",
        headers={
            "Origin": "http://testserver",
            "Sec-Fetch-Site": "same-origin",
        },
    )

    assert response.status_code == 200


def test_null_origin_browser_write_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/onboarding/complete",
        headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"},
    )

    assert response.status_code == 403


def test_first_run_onboarding_marker_is_explicitly_completed(
    tmp_path: Path, database_url: str
) -> None:
    marker = tmp_path / "first-run.pending"
    marker.write_text("pending", encoding="ascii")
    application = create_app(
        tmp_path / "missing-dist",
        database_url=database_url,
        material_dir=tmp_path / "materials",
        first_run_marker=marker,
    )

    with TestClient(application) as setup_client:
        settings_response = setup_client.get("/api/settings").json()
        assert "setup_pending" not in settings_response

        status_response = setup_client.get("/api/onboarding")
        assert status_response.status_code == 200
        assert status_response.json() == {"pending": True}

        complete_response = setup_client.post("/api/onboarding/complete")
        assert complete_response.status_code == 200
        assert complete_response.json() == {"pending": False}
        assert setup_client.get("/api/onboarding").json() == {"pending": False}

    assert not marker.exists()


def test_static_assets_and_spa_fallback(tmp_path: Path, database_url: str) -> None:
    static_dir = tmp_path / "dist"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<h1>Learning Flow Coach</h1>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ready')", encoding="utf-8")
    with TestClient(create_app(static_dir, database_url=database_url)) as client:
        assert client.get("/").text == "<h1>Learning Flow Coach</h1>"
        assert client.get("/status").text == "<h1>Learning Flow Coach</h1>"
        assert client.get("/assets/app.js").text == "console.log('ready')"
        assert client.get("/api/missing").status_code == 404


def test_restart_marks_stale_ai_runs_as_failed(tmp_path: Path, database_url: str) -> None:
    first_app = create_app(tmp_path / "missing-dist", database_url=database_url)
    with TestClient(first_app), first_app.state.session_factory() as session:
        session.add(
            AiRun(
                provider=AiProvider.CODEX,
                task=AiRunTask.PRACTICE_GENERATION,
                status=AiRunStatus.RUNNING,
                context_snapshot="context",
                prompt_text="prompt",
            )
        )
        session.commit()

    restarted_app = create_app(tmp_path / "missing-dist", database_url=database_url)
    with TestClient(restarted_app), restarted_app.state.session_factory() as session:
        ai_run = session.scalar(select(AiRun))

    assert ai_run is not None
    assert ai_run.status == AiRunStatus.FAILED
    assert ai_run.error_text == "服务已重新启动，原生成任务已中断，请重新生成。"
