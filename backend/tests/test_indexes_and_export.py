from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient


def create_learning_data(client: TestClient) -> tuple[dict, dict, dict, dict]:
    course = client.post(
        "/api/courses",
        json={
            "name": "概率论",
            "description": "研究随机现象",
            "learning_goal": "掌握条件概率",
        },
    ).json()
    chapter = client.post(f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}).json()
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "条件概率"}
    ).json()
    record = client.post(f"/api/sections/{section['id']}/daily-records/today").json()
    client.patch(
        f"/api/daily-records/{record['id']}",
        json={
            "recall_core_concepts": "条件概率定义",
            "study_material_scope": "教材第 1.2 节",
            "reconstruct_main_learning": "贝叶斯公式",
        },
    )
    exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    client.patch(
        f"/api/exercises/{exercise['id']}",
        json={
            "ai_questions": "何时可以使用贝叶斯公式？",
            "user_answers": "任何条件下都可以。",
            "ai_feedback": "需要先确认条件事件概率非零。",
        },
    )
    mistake = client.post(
        f"/api/exercises/{exercise['id']}/mistakes",
        json={
            "original_question": "何时可以使用贝叶斯公式？",
            "user_answer": "任何条件下都可以。",
            "error_content": "忽略了条件事件概率必须非零。",
            "error_type": "formula_condition",
            "correct_approach": "先检查条件事件概率，再应用公式。",
            "cause_analysis": "没有理解公式成立的前提。",
        },
    ).json()
    return course, chapter, section, {**record, "mistake_id": mistake["id"]}


def test_mistake_index_includes_course_chapter_and_section_context(
    client: TestClient,
) -> None:
    course, chapter, section, record = create_learning_data(client)
    empty_course = client.post("/api/courses", json={"name": "线性代数"}).json()
    empty_chapter = client.post(
        f"/api/courses/{empty_course['id']}/chapters", json={"title": "向量"}
    ).json()
    empty_section = client.post(
        f"/api/chapters/{empty_chapter['id']}/sections", json={"title": "线性相关"}
    ).json()

    response = client.get("/api/mistakes")

    assert response.status_code == 200
    body = response.json()
    assert body["courses"] == [
        {
            "id": course["id"],
            "name": "概率论",
            "chapters": [
                {
                    "id": chapter["id"],
                    "title": "第一章",
                    "sections": [{"id": section["id"], "title": "条件概率"}],
                }
            ],
        },
        {
            "id": empty_course["id"],
            "name": "线性代数",
            "chapters": [
                {
                    "id": empty_chapter["id"],
                    "title": "向量",
                    "sections": [{"id": empty_section["id"], "title": "线性相关"}],
                }
            ],
        },
    ]
    assert body["items"] == [
        {
            "id": record["mistake_id"],
            "exercise_id": 1,
            "daily_record_id": record["id"],
            "study_date": record["study_date"],
            "course_id": course["id"],
            "course_name": "概率论",
            "chapter_id": chapter["id"],
            "chapter_title": "第一章",
            "section_id": section["id"],
            "section_title": "条件概率",
            "original_question": "何时可以使用贝叶斯公式？",
            "user_answer": "任何条件下都可以。",
            "error_content": "忽略了条件事件概率必须非零。",
            "error_type": "formula_condition",
            "correct_approach": "先检查条件事件概率，再应用公式。",
            "cause_analysis": "没有理解公式成立的前提。",
            "status": "unresolved",
        }
    ]


def test_note_index_reads_only_tool_managed_section_paths(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    course = client.post("/api/courses", json={"name": "概率论"}).json()
    chapter = client.post(f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}).json()
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "条件概率"}
    ).json()
    assert client.get("/api/notes").status_code == 409
    assert (
        client.put("/api/settings/obsidian", json={"obsidian_vault_path": str(vault)}).status_code
        == 200
    )
    saved = client.put(
        f"/api/sections/{section['id']}/note",
        json={"content": "# 条件概率\n\n定义与适用条件。", "expected_modified_at_ns": None},
    )
    assert saved.status_code == 200
    (vault / "不属于工具的笔记.md").write_text("不应被索引", encoding="utf-8")

    response = client.get("/api/notes")

    assert response.status_code == 200
    body = response.json()
    assert body["issues"] == []
    assert len(body["items"]) == 1
    note = body["items"][0]
    assert note["section_id"] == section["id"]
    assert "daily_record_id" not in note
    assert note["relative_path"] == "概率论/第一章/条件概率.md"
    assert note["content"] == "# 条件概率\n\n定义与适用条件。"


def test_markdown_export_contains_outline_records_exercises_and_mistakes(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    course, _, section, record = create_learning_data(client)
    client.post("/api/courses", json={"name": "不导出的课程"})
    assert (
        client.put("/api/settings/obsidian", json={"obsidian_vault_path": str(vault)}).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/sections/{section['id']}/note",
            json={"content": "# 条件概率笔记", "expected_modified_at_ns": None},
        ).status_code
        == 200
    )

    response = client.post(
        "/api/export/archive",
        json={
            "course_ids": [course["id"]],
            "content_types": [
                "outline",
                "daily_records",
                "ai_reviews",
                "exercises",
                "mistakes",
                "notes",
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert 'attachment; filename="learning-flow-export-' in response.headers["content-disposition"]
    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        section_root = "01-概率论/01-第一章/01-条件概率"
        assert "导出说明.md" in names
        assert "01-概率论/课程概览.md" in names
        assert f"{section_root}/学习记录/{record['study_date']}.md" in names
        assert f"{section_root}/练习与批改/{record['study_date']}-练习01.md" in names
        assert f"{section_root}/错题.md" in names
        assert f"{section_root}/小节笔记.md" in names
        assert not any("不导出的课程" in name for name in names)
        assert (
            "教材第 1.2 节"
            in archive.read(f"{section_root}/学习记录/{record['study_date']}.md").decode()
        )
        assert "忽略了条件事件概率必须非零" in archive.read(f"{section_root}/错题.md").decode()
        assert archive.read(f"{section_root}/小节笔记.md").decode() == "# 条件概率笔记"


def test_markdown_archive_validates_selection_and_content(client: TestClient) -> None:
    course, _, _, _ = create_learning_data(client)
    assert (
        client.post(
            "/api/export/archive",
            json={"course_ids": [], "content_types": ["mistakes"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/export/archive",
            json={"course_ids": [course["id"]], "content_types": []},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/export/archive",
            json={"course_ids": [999], "content_types": ["mistakes"]},
        ).status_code
        == 422
    )

    response = client.post(
        "/api/export/archive",
        json={"course_ids": [course["id"]], "content_types": ["mistakes"]},
    )
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "01-概率论/01-第一章/01-条件概率/错题.md" in names
        assert "01-概率论/课程概览.md" not in names
        assert not any("/学习记录/" in name for name in names)
