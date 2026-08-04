import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.api as api_module
import app.materials as materials_module
from app.ai_providers import AiProviderError, AiProviderResult
from app.ai_workflows import build_task_context, used_source_references
from app.materials import MaterialError, MaterialReference, extract_html, revision_hash
from app.models import AiRunTask, DailyRecord, DailyRecordMaterial, LearningMaterial
from app.search_index import EMBEDDING_MODEL, SearchDocument, hybrid_rank_bonuses


class MaterialSessionCodex:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.calls: list[dict] = []

    async def generate(
        self,
        prompt: str,
        output_schema: dict | None = None,
        **options,
    ) -> AiProviderResult:
        call_number = len(self.calls) + 1
        self.calls.append({"prompt": prompt, "schema": output_schema, **options})
        thread_id = options.get("resume_thread_id") or f"thread-{call_number}"
        properties = output_schema.get("properties", {}) if output_schema else {}
        if "coverage_markdown" in properties:
            text = json.dumps({"coverage_markdown": "材料已完整读取"}, ensure_ascii=False)
        elif "items" in properties:
            text = json.dumps(
                {
                    "items": [
                        {
                            "position": position,
                            "item_type": "single_choice" if position <= 4 else "short_answer",
                            "difficulty": "basic",
                            "stem_markdown": f"Question {position}",
                            "options": (
                                [{"id": "A", "label": "Option A"}]
                                if position <= 4
                                else []
                            ),
                            "answer_key": {
                                "selected_options": ["A"] if position <= 4 else [],
                                "answer_markdown": "Reference answer",
                            },
                            "rubric_markdown": "Rubric",
                            "source_refs": [],
                        }
                        for position in range(1, 13)
                    ],
                    "handoff": {
                        "confirmed_points": [],
                        "corrections": [],
                        "key_concepts": [],
                        "key_formulas": [],
                        "unresolved_points": [],
                        "error_patterns": [],
                        "source_refs": [],
                    },
                },
                ensure_ascii=False,
            )
        else:
            handoff = {
                "confirmed_points": [],
                "corrections": [],
                "key_concepts": [],
                "key_formulas": [],
                "unresolved_points": [],
                "error_patterns": [],
                "source_refs": [],
            }
            text = json.dumps(
                {"display_markdown": "练习内容", "handoff": handoff},
                ensure_ascii=False,
            )
        return AiProviderResult(
            text=text,
            model="fake-codex",
            thread_id=thread_id,
            turn_id=f"turn-{call_number}",
        )


class MaterialSessionAiService:
    def __init__(self, workspace: Path) -> None:
        self.codex = MaterialSessionCodex(workspace)

    async def close(self) -> None:
        return None


def create_learning_scope(client: TestClient) -> tuple[dict, dict, dict, dict]:
    course = client.post(
        "/api/courses",
        json={"name": "材料课程", "description": "", "learning_goal": "理解线性代数"},
    ).json()
    chapter = client.post(
        f"/api/courses/{course['id']}/chapters",
        json={"title": "第一章"},
    ).json()
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections",
        json={"title": "向量空间"},
    ).json()
    record = client.post(f"/api/sections/{section['id']}/daily-records/today").json()
    return course, chapter, section, record


def fake_page(url: str) -> tuple[str, str, bytes]:
    return (
        url,
        "线性代数教材",
        (
            b"<html><head><title>Linear Algebra</title></head><body><main>"
            b"<h1>Vector Space</h1>"
            b"<p>A vector space is closed under addition and scalar multiplication.</p>"
            b"<p>Basis vectors are linearly independent and span the space.</p>"
            b"</main></body></html>"
        ),
    )


def test_material_session_incremental_add_and_rebuild_on_refresh(
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
    monkeypatch,
) -> None:
    pages = iter(
        [
            ("https://example.test/one", "材料一", b"<main>first material body</main>"),
            ("https://example.test/two", "材料二", b"<main>second material body</main>"),
            ("https://example.test/one", "材料一", b"<main>replaced material body</main>"),
        ]
    )
    monkeypatch.setattr(api_module, "fetch_url", lambda _: next(pages))
    service = MaterialSessionAiService(tmp_path / "ai-workspace")
    app.state.ai_service = service
    course, chapter, section, record = create_learning_scope(client)

    first = client.post(
        "/api/materials/url",
        json={
            "title": "材料一",
            "url": "https://example.test/one",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    ).json()
    assert client.post(f"/api/daily-records/{record['id']}/ai-practice").status_code == 201
    (first_node,) = service.codex.calls
    assert "fork_thread_id" not in first_node
    assert first_node["persistent"] is True
    assert first_node["readable_roots"]
    assert "first material body" in first_node["prompt"]
    assert "[M" in first_node["prompt"]

    client.post(
        "/api/materials/url",
        json={
            "title": "材料二",
            "url": "https://example.test/two",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    )
    assert client.post(f"/api/daily-records/{record['id']}/ai-practice").status_code == 201
    second_node = service.codex.calls[1]
    assert second_node["fork_thread_id"] == "thread-1"
    assert second_node["fork_last_turn_id"] == "turn-1"
    assert "材料二" in second_node["prompt"]

    assert client.post(f"/api/materials/{first['id']}/refresh").status_code == 200
    assert client.post(f"/api/daily-records/{record['id']}/ai-practice").status_code == 201
    third_node = service.codex.calls[2]
    assert "fork_thread_id" not in third_node
    assert third_node["readable_roots"]
    assert "replaced material body" in third_node["prompt"]


def test_material_session_recovers_when_saved_thread_is_no_longer_available(
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api_module, "fetch_url", fake_page)
    service = MaterialSessionAiService(tmp_path / "ai-workspace")
    app.state.ai_service = service
    course, chapter, section, record = create_learning_scope(client)
    client.post(
        "/api/materials/url",
        json={
            "title": "材料一",
            "url": "https://example.test/one",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    )
    assert client.post(f"/api/daily-records/{record['id']}/ai-practice").status_code == 201

    original_generate = service.codex.generate
    stale_thread_seen = False

    async def generate_with_stale_thread(*args, **kwargs):
        nonlocal stale_thread_seen
        if kwargs.get("fork_thread_id") and not stale_thread_seen:
            stale_thread_seen = True
            raise AiProviderError("no rollout found for thread id thread-1")
        return await original_generate(*args, **kwargs)

    monkeypatch.setattr(service.codex, "generate", generate_with_stale_thread)
    response = client.post(f"/api/daily-records/{record['id']}/ai-practice")

    assert response.status_code == 201
    assert stale_thread_seen is True
    recovered_call = service.codex.calls[-1]
    assert "fork_thread_id" not in recovered_call
    assert recovered_call["persistent"] is True


def test_url_fetch_uses_repaired_proxy_without_trusting_stale_environment(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/html"},
                content=(
                    b"<html><head><title>Example</title></head>"
                    b"<body><main>Study text</main></body></html>"
                ),
            )

    monkeypatch.setattr(materials_module, "validate_public_url", lambda _: None)
    monkeypatch.setattr(
        materials_module,
        "build_subprocess_environment",
        lambda: {"HTTPS_PROXY": "http://127.0.0.1:7897"},
    )
    monkeypatch.setattr(materials_module.httpx, "Client", FakeClient)

    final_url, title, _ = materials_module.fetch_url("https://example.test")

    assert final_url == "https://example.test"
    assert title == "Example"
    assert captured["proxy"] == "http://127.0.0.1:7897"
    assert captured["trust_env"] is False


def test_url_fetch_retries_rate_limit_using_retry_after(monkeypatch) -> None:
    attempts = 0
    delays: list[float] = []

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            request = httpx.Request("GET", url)
            if attempts < 3:
                return httpx.Response(429, request=request, headers={"retry-after": "0.25"})
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/html"},
                content=b"<html><body><main>Recovered material</main></body></html>",
            )

    monkeypatch.setattr(materials_module, "validate_public_url", lambda _: None)
    monkeypatch.setattr(materials_module, "build_subprocess_environment", lambda: {})
    monkeypatch.setattr(materials_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(materials_module.time, "sleep", delays.append)

    final_url, _, _ = materials_module.fetch_url("https://example.test/rate-limited")

    assert final_url == "https://example.test/rate-limited"
    assert attempts == 3
    assert delays == [0.25, 0.25]


def test_scanned_pdf_pages_use_cached_ocr_text(tmp_path: Path, monkeypatch) -> None:
    class FakePage:
        images = [object()]

        def extract_text(self) -> str:
            return ""

    class FakeReader:
        pages = [FakePage()]

    source = tmp_path / "versions" / "scan.pdf"
    source.parent.mkdir()
    source.write_bytes(b"%PDF-scanned-fixture")
    calls: list[int] = []
    monkeypatch.setattr(materials_module, "PdfReader", lambda _: FakeReader())
    monkeypatch.setattr(
        materials_module,
        "_ocr_pdf_page",
        lambda _path, page_index: calls.append(page_index) or "OCR 识别出的线性代数正文",
    )

    first = materials_module.extract_pdf(source)
    second = materials_module.extract_pdf(source)

    assert first == second
    assert first[0][1] == 1
    assert "OCR 识别" in first[0][2]
    assert calls == [0]
    assert len(list((tmp_path / "ocr-cache").glob("*.txt"))) == 1


def test_scanned_pdf_without_tesseract_has_actionable_retry_message(monkeypatch) -> None:
    monkeypatch.setattr(materials_module, "_tesseract_executable", lambda: None)

    with pytest.raises(MaterialError, match="内置 OCR 运行时.*修复"):
        materials_module._ocr_pdf_page(Path("scan.pdf"), 0)


def test_mixed_pdf_keeps_usable_pages_when_one_ocr_page_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakePage:
        images = [object()]

        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        pages = [
            FakePage("Native page text " * 10),
            FakePage(""),
            FakePage(""),
        ]

    source = tmp_path / "versions" / "mixed.pdf"
    source.parent.mkdir()
    source.write_bytes(b"%PDF-mixed-fixture")
    monkeypatch.setattr(materials_module, "PdfReader", lambda _: FakeReader())

    def fake_ocr(_path: Path, page_index: int) -> str:
        if page_index == 1:
            raise MaterialError("page failed")
        return "第三页 OCR 正文"

    monkeypatch.setattr(materials_module, "_ocr_pdf_page", fake_ocr)

    result = materials_module.extract_pdf_detailed(source)

    assert result.total_pages == 3
    assert result.ocr_pages == 2
    assert result.failed_pages == (2,)
    assert {chunk[1] for chunk in result.chunks} == {1, 3}
    assert "第 2 页" in result.warning_text


def test_hybrid_index_uses_local_full_text_and_keeps_primary_database_canonical(
    app: FastAPI, client: TestClient,
) -> None:
    del client
    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        bonuses = hybrid_rank_bonuses(
            session,
            [
                SearchDocument("probability", "条件概率定义与贝叶斯公式推导"),
                SearchDocument("geometry", "向量空间中的正交投影"),
            ],
            "条件概率定义",
        )
        sidecar = session.get_bind().url.database

    assert bonuses["probability"] > bonuses.get("geometry", 0)
    assert Path(sidecar).with_name("search-index.db").is_file()


def test_semantic_search_setting_requires_model_and_can_be_disabled(
    client: TestClient,
    monkeypatch,
) -> None:
    prepared_cache: Path | None = None

    def fake_prepare(index: Path, cache: Path) -> None:
        nonlocal prepared_cache
        prepared_cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        model_dir = cache / "model-snapshot"
        model_dir.mkdir()
        (model_dir / "model_optimized.onnx").write_bytes(b"model")
        (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        with sqlite3.connect(index) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('model_ready', ?)",
                (EMBEDDING_MODEL,),
            )

    initial = client.get("/api/settings/material-search")
    assert initial.status_code == 200
    assert initial.json()["semantic_enabled"] is False
    assert initial.json()["model_ready"] is False

    monkeypatch.setattr(api_module, "prepare_semantic_model_paths", fake_prepare)
    enabled = client.post("/api/settings/material-search/enable")
    assert enabled.status_code == 200
    assert enabled.json()["semantic_enabled"] is True
    assert enabled.json()["model_ready"] is True
    assert client.get("/api/settings").json()["semantic_search_enabled"] is True

    disabled = client.post("/api/settings/material-search/disable")
    assert disabled.status_code == 200
    assert disabled.json()["semantic_enabled"] is False
    assert disabled.json()["model_ready"] is True

    assert prepared_cache is not None
    next(prepared_cache.rglob("model_optimized.onnx")).unlink()
    missing = client.get("/api/settings/material-search")
    assert missing.status_code == 200
    assert missing.json()["model_ready"] is False


def test_semantic_search_model_failure_does_not_enable_setting(
    client: TestClient,
    monkeypatch,
) -> None:
    def fail_prepare(_index: Path, _cache: Path) -> None:
        raise OSError("download unavailable")

    monkeypatch.setattr(api_module, "prepare_semantic_model_paths", fail_prepare)
    response = client.post("/api/settings/material-search/enable")

    assert response.status_code == 503
    assert "模型准备失败" in response.json()["detail"]
    assert client.get("/api/settings/material-search").json()["semantic_enabled"] is False


def test_failed_url_material_is_kept_and_can_be_reparsed(
    client: TestClient,
    monkeypatch,
) -> None:
    calls = 0

    def fetch_with_retry(url: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise MaterialError("暂时无法读取原链接")
        return fake_page(url)

    monkeypatch.setattr(api_module, "fetch_url", fetch_with_retry)
    course, chapter, section, _ = create_learning_scope(client)
    created = client.post(
        "/api/materials/url",
        json={
            "title": "可重试材料",
            "url": "https://example.test/retry",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    )

    assert created.status_code == 201
    failed = created.json()
    assert failed["status"] == "failed"
    assert failed["chunk_count"] == 0
    assert "暂时无法读取原链接" in failed["error_text"]

    reparsed = client.post(f"/api/materials/{failed['id']}/refresh")
    assert reparsed.status_code == 200
    assert reparsed.json()["refresh_status"] == "succeeded"
    assert reparsed.json()["material"]["status"] == "ready"
    assert reparsed.json()["material"]["chunk_count"] > 0
    assert reparsed.json()["material"]["is_primary"] is True


def test_url_material_scope_selection_and_ai_context(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api_module, "fetch_url", fake_page)
    course, chapter, section, record = create_learning_scope(client)

    created = client.post(
        "/api/materials/url",
        json={
            "title": "线性代数教材",
            "url": "https://example.test/linear-algebra",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
            "is_primary": True,
        },
    )
    assert created.status_code == 201
    material = created.json()
    assert material["status"] == "ready"
    assert material["chunk_count"] > 0
    assert material["is_primary"] is True

    loaded = client.get(f"/api/daily-records/{record['id']}").json()
    assert loaded["materials"][0]["selected"] is True

    exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    assert "【本次参考材料】" in exercise["generation_prompt"]
    assert "linearly independent" in exercise["generation_prompt"]

    manual_note = client.post(
        f"/api/daily-records/{record['id']}/section-note-prompt",
        json={"existing_content": "", "mode": "create"},
    )
    assert manual_note.status_code == 200
    assert "【当前小节完整材料】" in manual_note.json()["prompt_text"]
    assert "closed under addition" in manual_note.json()["prompt_text"]
    assert "linearly independent" in manual_note.json()["prompt_text"]

    disabled = client.put(
        f"/api/daily-records/{record['id']}/materials/{material['id']}",
        json={"selected": False, "range_note": ""},
    )
    assert disabled.status_code == 200
    assert disabled.json()["materials"][0]["selected"] is False

    without_material = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    assert "【本次参考材料】" not in without_material["generation_prompt"]

    enabled = client.put(
        f"/api/daily-records/{record['id']}/materials/{material['id']}",
        json={"selected": True, "range_note": "basis vectors"},
    )
    assert enabled.json()["materials"][0]["range_note"] == "basis vectors"

    duplicate = client.post(
        "/api/materials/url",
        json={
            "title": "重复材料",
            "url": "https://example.test/linear-algebra",
            "course_id": course["id"],
        },
    )
    assert duplicate.status_code == 409

    refreshed = client.post(f"/api/materials/{material['id']}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["material"]["chunk_count"] > 0

    assert client.delete(f"/api/materials/{material['id']}").status_code == 204
    assert client.get("/api/materials").json() == []


def test_first_material_in_a_scope_becomes_primary(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api_module, "fetch_url", fake_page)
    course, chapter, section, _ = create_learning_scope(client)

    created = client.post(
        "/api/materials/url",
        json={
            "title": "第一份材料",
            "url": "https://example.test/first",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
            "is_primary": False,
        },
    )

    assert created.status_code == 201
    assert created.json()["is_primary"] is True


def test_multiple_ready_materials_can_be_marked_as_priority(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api_module,
        "fetch_url",
        lambda url: (
            url,
            "Priority material",
            f"<html><main>Distinct content for {url}</main></html>".encode(),
        ),
    )
    course, chapter, section, _ = create_learning_scope(client)
    payload = {
        "course_id": course["id"],
        "chapter_id": chapter["id"],
        "section_id": section["id"],
    }
    first = client.post(
        "/api/materials/url",
        json={**payload, "title": "重点一", "url": "https://example.test/priority-one"},
    ).json()
    second = client.post(
        "/api/materials/url",
        json={**payload, "title": "重点二", "url": "https://example.test/priority-two"},
    ).json()

    assert first["is_primary"] is True
    assert second["is_primary"] is False
    promoted = client.patch(
        f"/api/materials/{second['id']}",
        json={"is_primary": True},
    )
    assert promoted.status_code == 200

    materials = client.get(f"/api/materials?course_id={course['id']}").json()
    assert {item["title"] for item in materials if item["is_primary"]} == {"重点一", "重点二"}


def test_material_scope_validation_and_failed_pdf(
    client: TestClient,
) -> None:
    course, chapter, section, _ = create_learning_scope(client)
    other_course = client.post(
        "/api/courses",
        json={"name": "其他课程", "description": "", "learning_goal": ""},
    ).json()

    invalid_scope = client.post(
        "/api/materials/url",
        json={
            "title": "错误范围",
            "url": "https://example.test/content",
            "course_id": other_course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    )
    assert invalid_scope.status_code == 422

    invalid_pdf = client.post(
        "/api/materials/pdf",
        data={
            "title": "错误 PDF",
            "course_id": str(course["id"]),
            "chapter_id": str(chapter["id"]),
            "section_id": str(section["id"]),
        },
        files={"file": ("material.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert invalid_pdf.status_code == 422


def test_deleting_course_removes_material_storage(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api_module, "fetch_url", fake_page)
    course, chapter, section, _ = create_learning_scope(client)
    material = client.post(
        "/api/materials/url",
        json={
            "title": "待清理材料",
            "url": "https://example.test/cleanup",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    ).json()
    storage_directory = client.app.state.material_dir / str(material["id"])
    assert storage_directory.is_dir()

    assert client.delete(f"/api/courses/{course['id']}").status_code == 204
    assert not storage_directory.exists()


def test_video_url_is_saved_as_timestamped_transcript(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api_module,
        "fetch_video_transcript",
        lambda url: (
            url,
            "公开视频",
            b"WEBVTT\n\n00:00.000 --> 00:30.000\nvector basis",
            [("00:00-00:30", None, "vector basis")],
        ),
    )
    course, chapter, section, record = create_learning_scope(client)
    created = client.post(
        "/api/materials/url",
        json={
            "title": "视频讲解",
            "url": "https://www.youtube.com/watch?v=example",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    )

    assert created.status_code == 201
    assert created.json()["source_type"] == "video"
    assert created.json()["chunk_count"] == 1
    exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    assert "00:00-00:30" in exercise["generation_prompt"]


def test_ready_material_keeps_active_revision_when_refresh_fails(
    client: TestClient,
    app: FastAPI,
    monkeypatch,
) -> None:
    calls = 0

    def fetch_then_fail(url: str):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise MaterialError("读取视频字幕失败：HTTP Error 429")
        return fake_page(url)

    monkeypatch.setattr(api_module, "fetch_url", fetch_then_fail)
    course, chapter, section, record = create_learning_scope(client)
    material = client.post(
        "/api/materials/url",
        json={
            "title": "可用网页",
            "url": "https://example.test/rate-limited",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    ).json()
    with app.state.session_factory() as session:
        active_hash = session.get(LearningMaterial, material["id"]).content_hash

    refreshed = client.post(f"/api/materials/{material['id']}/refresh")
    payload = refreshed.json()
    assert payload["refresh_status"] == "failed"
    assert payload["using_previous_revision"] is True
    assert payload["material"]["status"] == "ready"
    assert payload["material"]["chunk_count"] > 0
    assert "429" in payload["material"]["last_refresh_error"]
    with app.state.session_factory() as session:
        stored = session.get(LearningMaterial, material["id"])
        assert stored.content_hash == active_hash
    exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    assert "linearly independent" in exercise["generation_prompt"]


def test_html_extraction_prefers_embedded_transcript_and_versions_parser_output() -> None:
    content = b"""
    <html><body><main><h2>Overview</h2><p>Short overview.</p></main>
    <div class="element-hidden"><div id="inline_content">
      <h1 id="transcript-top">Course transcript</h1>
      <h3>Chapter 1 [00:00:00]</h3><p>First transcript section with durable evidence.</p>
      <h3>Chapter 2 [00:06:12]</h3><p>Second transcript section with further evidence.</p>
      <p>""" + b"long transcript evidence " * 40 + b"""</p>
    </div></div></body></html>
    """

    extraction = extract_html(content)
    assert extraction.profile == "transcript"
    assert len(extraction.chunks) >= 2
    combined = " ".join(chunk[2] for chunk in extraction.chunks)
    assert "First transcript section" in combined
    assert "Short overview" not in combined
    source_digest = materials_module.content_hash(content)
    assert revision_hash(source_digest, extraction.chunks, "parser-a") != revision_hash(
        source_digest, extraction.chunks, "parser-b"
    )


def test_structured_source_refs_resolve_only_authorized_chunk_positions() -> None:
    candidates = [
        MaterialReference(1, "讲义", "pdf", "第 2 页", "hash-a", 2),
        MaterialReference(1, "讲义", "pdf", "第 3 页", "hash-a", 3),
        MaterialReference(2, "视频", "video", "00:05-00:08", "hash-b", 4),
    ]
    payload = {
        "handoff": {
            "source_refs": [
                {
                    "material_id": 1,
                    "chunk_positions": [3, 99],
                    "evidence_summary": "使用第三页定义",
                },
                {
                    "material_id": 999,
                    "chunk_positions": [1],
                    "evidence_summary": "不存在的材料",
                },
            ]
        }
    }

    matched = used_source_references(candidates, payload)
    assert [(item.material_id, item.chunk_position, item.location) for item in matched] == [
        (1, 3, "第 3 页")
    ]


def test_recall_uses_previous_record_material_version(
    client: TestClient,
    app: FastAPI,
    monkeypatch,
) -> None:
    pages = iter(
        [
            (
                "https://example.test/versioned",
                "版本材料",
                b"<html><main>old theorem condition and proof</main></html>",
            ),
            (
                "https://example.test/versioned",
                "版本材料",
                b"<html><main>new replacement content</main></html>",
            ),
        ]
    )
    monkeypatch.setattr(api_module, "fetch_url", lambda _: next(pages))
    course, chapter, section, current = create_learning_scope(client)
    material = client.post(
        "/api/materials/url",
        json={
            "title": "版本材料",
            "url": "https://example.test/versioned",
            "course_id": course["id"],
            "chapter_id": chapter["id"],
            "section_id": section["id"],
        },
    ).json()

    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        stored = session.get(LearningMaterial, material["id"])
        previous = DailyRecord(
            section_id=section["id"],
            study_date=date.today() - timedelta(days=1),
        )
        session.add(previous)
        session.flush()
        session.add(
            DailyRecordMaterial(
                daily_record_id=previous.id,
                material_id=stored.id,
                enabled=True,
                content_hash=stored.content_hash,
            )
        )
        old_hash = stored.content_hash
        session.commit()

    assert client.post(f"/api/materials/{material['id']}/refresh").status_code == 200

    with session_factory() as session:
        record = session.get(DailyRecord, current["id"])
        context = build_task_context(session, record, AiRunTask.RECALL_REVIEW)
        assert "old theorem condition" in context.text
        assert "new replacement content" not in context.text
        assert context.source_refs[0].content_hash == old_hash
