import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.vaults import inspect_vault


def create_record(client: TestClient, course_name: str = "概率论") -> tuple[dict, dict]:
    course = client.post("/api/courses", json={"name": course_name}).json()
    chapter = client.post(f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}).json()
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "条件概率"}
    ).json()
    record = client.post(f"/api/sections/{section['id']}/daily-records/today").json()
    return section, record


def configure_vault(client: TestClient, vault: Path) -> None:
    response = client.put("/api/settings/obsidian", json={"obsidian_vault_path": str(vault)})
    assert response.status_code == 200
    assert Path(response.json()["obsidian_vault_path"]) == vault.resolve()


def test_settings_note_read_write_and_external_conflict(client: TestClient, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    section, _ = create_record(client)

    assert client.get("/api/settings").json() == {
        "obsidian_vault_path": "",
        "learner_profile": "",
        "service_version": "0.1.3",
        "desktop_launch": False,
        "semantic_search_enabled": False,
        "semantic_search_model_ready": False,
    }
    assert (
        client.put(
            "/api/settings/obsidian", json={"obsidian_vault_path": "relative/path"}
        ).status_code
        == 422
    )
    assert client.get(f"/api/sections/{section['id']}/note").status_code == 409
    configure_vault(client, vault)

    note_url = f"/api/sections/{section['id']}/note"
    opened = client.get(note_url).json()
    assert opened["relative_path"] == "概率论/第一章/条件概率.md"
    assert opened["content"] == ""
    assert opened["modified_at_ns"] is None

    response = client.put(
        note_url,
        json={
            "content": "# 条件概率\n\n定义与适用条件。",
            "expected_modified_at_ns": None,
        },
    )
    assert response.status_code == 200
    saved = response.json()
    note_path = vault / "概率论" / "第一章" / "条件概率.md"
    assert note_path.read_text(encoding="utf-8") == saved["content"]
    assert saved["modified_at_ns"] is not None

    note_path.write_text("# Obsidian 外部修改", encoding="utf-8")
    conflict_payload = {
        "content": "# Web 中的旧版本",
        "expected_modified_at_ns": saved["modified_at_ns"],
    }
    response = client.put(note_url, json=conflict_payload)
    assert response.status_code == 409
    assert "外部修改" in response.json()["detail"]
    assert note_path.read_text(encoding="utf-8") == "# Obsidian 外部修改"

    response = client.put(note_url, json={**conflict_payload, "force_overwrite": True})
    assert response.status_code == 200
    assert note_path.read_text(encoding="utf-8") == "# Web 中的旧版本"


def test_note_path_maps_unsafe_titles_and_same_chapter_duplicates(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    configure_vault(client, vault)

    unsafe_section, _ = create_record(client, course_name="课程:非法")
    response = client.get(f"/api/sections/{unsafe_section['id']}/note")
    assert response.status_code == 200
    unsafe_note = response.json()
    assert unsafe_note["relative_path"].startswith("课程：非法--c")
    assert ":" not in unsafe_note["relative_path"]
    saved = client.put(
        f"/api/sections/{unsafe_section['id']}/note",
        json={"content": "# 可索引笔记", "expected_modified_at_ns": None},
    )
    assert saved.status_code == 200
    assert (vault.joinpath(*unsafe_note["relative_path"].split("/"))).is_file()
    note_index = client.get("/api/notes").json()
    assert note_index["issues"] == []
    assert any(item["section_id"] == unsafe_section["id"] for item in note_index["items"])

    course = client.post("/api/courses", json={"name": "线性代数"}).json()
    first_chapter = client.post(
        f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}
    ).json()
    first = client.post(
        f"/api/chapters/{first_chapter['id']}/sections", json={"title": "向量"}
    ).json()
    second = client.post(
        f"/api/chapters/{first_chapter['id']}/sections", json={"title": "向量"}
    ).json()
    first_note = client.get(f"/api/sections/{first['id']}/note")
    second_note = client.get(f"/api/sections/{second['id']}/note")
    assert first_note.status_code == 200
    assert second_note.status_code == 200
    assert first_note.json()["relative_path"] != second_note.json()["relative_path"]
    assert second_note.json()["file_name"].endswith(f"--s{second['id']}.md")


def test_note_path_handles_reserved_and_long_titles(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    configure_vault(client, vault)
    course = client.post("/api/courses", json={"name": "CON"}).json()
    chapter = client.post(
        f"/api/courses/{course['id']}/chapters",
        json={"title": "NUL"},
    ).json()
    long_title = "Class: " + ("Very long topic " * 20)
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections",
        json={"title": long_title[:200]},
    ).json()

    response = client.get(f"/api/sections/{section['id']}/note")

    assert response.status_code == 200
    note = response.json()
    parts = note["relative_path"].split("/")
    assert len(parts) == 3
    assert all(len(part.removesuffix(".md")) <= 200 for part in parts)
    assert parts[0].startswith("＿CON")
    assert parts[1].startswith("＿NUL")
    assert ":" not in note["relative_path"]
    assert "Very long topic" in note["file_name"]
    assert note["file_name"] == parts[-1]


def test_note_path_remains_reachable_after_titles_are_renamed(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    section, _ = create_record(client)
    configure_vault(client, vault)
    note_url = f"/api/sections/{section['id']}/note"
    opened = client.get(note_url).json()
    saved = client.put(
        note_url,
        json={
            "content": "# 已保存笔记",
            "expected_modified_at_ns": opened["modified_at_ns"],
        },
    ).json()
    course_id = client.get("/api/courses").json()[0]["id"]
    chapter_id = section["chapter_id"]

    assert client.patch(f"/api/courses/{course_id}", json={"name": "新课程名"}).status_code == 200
    assert (
        client.patch(f"/api/chapters/{chapter_id}", json={"title": "新章节名"}).status_code
        == 200
    )
    assert client.patch(
        f"/api/sections/{section['id']}",
        json={"title": "新小节名"},
    ).status_code == 200

    reopened = client.get(note_url)
    assert reopened.status_code == 200
    assert reopened.json()["content"] == "# 已保存笔记"
    assert reopened.json()["relative_path"] == saved["relative_path"]


def test_note_write_supports_a_deep_windows_vault(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path
    for index in range(2):
        vault /= f"deep-vault-segment-{index}-with-a-readable-name"
    vault.mkdir(parents=True)
    section, _ = create_record(
        client,
        course_name="A long course title: " + ("probability " * 10),
    )
    configure_vault(client, vault)
    note_url = f"/api/sections/{section['id']}/note"
    opened = client.get(note_url).json()

    response = client.put(
        note_url,
        json={
            "content": "# 深层 Vault 笔记",
            "expected_modified_at_ns": opened["modified_at_ns"],
        },
    )

    assert response.status_code == 200
    saved = response.json()
    assert saved["content"] == "# 深层 Vault 笔记"
    assert client.get(note_url).json()["content"] == "# 深层 Vault 笔记"


def test_note_path_allows_same_title_in_different_chapters(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    configure_vault(client, vault)
    course = client.post("/api/courses", json={"name": "线性代数"}).json()
    first_chapter = client.post(
        f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}
    ).json()
    second_chapter = client.post(
        f"/api/courses/{course['id']}/chapters", json={"title": "第二章"}
    ).json()
    first = client.post(
        f"/api/chapters/{first_chapter['id']}/sections", json={"title": "向量"}
    ).json()
    second = client.post(
        f"/api/chapters/{second_chapter['id']}/sections", json={"title": "向量"}
    ).json()

    first_note = client.get(f"/api/sections/{first['id']}/note").json()
    second_note = client.get(f"/api/sections/{second['id']}/note").json()
    assert first_note["relative_path"] == "线性代数/第一章/向量.md"
    assert second_note["relative_path"] == "线性代数/第二章/向量.md"


def test_legacy_note_is_read_then_migrated_on_save(client: TestClient, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    section, _ = create_record(client)
    configure_vault(client, vault)
    legacy_path = vault / "概率论" / "条件概率.md"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text("# 旧版笔记", encoding="utf-8")

    note_url = f"/api/sections/{section['id']}/note"
    opened = client.get(note_url).json()
    assert opened["content"] == "# 旧版笔记"
    assert opened["relative_path"] == "概率论/第一章/条件概率.md"

    response = client.put(
        note_url,
        json={
            "content": "# 迁移后的笔记",
            "expected_modified_at_ns": opened["modified_at_ns"],
        },
    )
    assert response.status_code == 200
    assert not legacy_path.exists()
    assert (vault / "概率论" / "第一章" / "条件概率.md").read_text(
        encoding="utf-8"
    ) == "# 迁移后的笔记"


def test_new_and_legacy_note_conflict_is_not_overwritten(
    client: TestClient, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    section, _ = create_record(client)
    configure_vault(client, vault)
    legacy_path = vault / "概率论" / "条件概率.md"
    current_path = vault / "概率论" / "第一章" / "条件概率.md"
    current_path.parent.mkdir(parents=True)
    legacy_path.write_text("旧版", encoding="utf-8")
    current_path.write_text("新版", encoding="utf-8")

    response = client.get(f"/api/sections/{section['id']}/note")
    assert response.status_code == 409
    assert "新旧两份" in response.json()["detail"]
    assert legacy_path.read_text(encoding="utf-8") == "旧版"
    assert current_path.read_text(encoding="utf-8") == "新版"


def test_section_note_prompt_is_generated_and_persisted(client: TestClient) -> None:
    _, record = create_record(client)
    client.patch(
        f"/api/daily-records/{record['id']}",
        json={
            "reconstruct_problem": "解释条件信息如何改变概率",
            "reconstruct_main_learning": "条件概率定义",
        },
    )
    response = client.post(f"/api/daily-records/{record['id']}/section-note-prompt")
    assert response.status_code == 200
    assert "条件概率定义" in response.json()["prompt_text"]
    assert "独立公式块使用 `$$...$$`" in response.json()["prompt_text"]
    assert "不要省略花括号" in response.json()["prompt_text"]
    assert "笔记正文不要输出材料引用、来源标记或来源清单" in response.json()["prompt_text"]
    assert "`handoff.source_refs` 只保留本次实际使用过的材料分块" in response.json()["prompt_text"]
    assert "在展示内容中用 `[材料标题" not in response.json()["prompt_text"]

    refreshed = client.get(f"/api/daily-records/{record['id']}").json()
    assert refreshed["section_note_prompt"]["id"] == response.json()["id"]


def test_discovers_and_browses_obsidian_vaults(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "Research Notes"
    (vault / ".obsidian").mkdir(parents=True)
    config = tmp_path / "obsidian.json"
    config.write_text(
        json.dumps({"vaults": {"one": {"path": str(vault)}, "missing": {"path": "Z:/missing"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.vaults.obsidian_config_paths", lambda: [config])
    monkeypatch.setattr("app.api.vault_browser_supported", lambda: True)
    monkeypatch.setattr("app.api.browse_for_vault", lambda: inspect_vault(vault))

    response = client.get("/api/settings/obsidian-vaults")
    assert response.status_code == 200
    assert response.json() == {
        "vaults": [
            {
                "name": "Research Notes",
                "path": str(vault.resolve()),
                "has_obsidian_directory": True,
                "writable": True,
            }
        ],
        "browse_supported": True,
    }

    response = client.post("/api/settings/obsidian/browse")
    assert response.status_code == 200
    assert response.json()["vault"]["path"] == str(vault.resolve())


def test_browse_obsidian_vault_can_be_cancelled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.api.browse_for_vault", lambda: None)
    response = client.post("/api/settings/obsidian/browse")
    assert response.status_code == 200
    assert response.json() == {"vault": None}
