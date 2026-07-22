from __future__ import annotations

import argparse
import json
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

import httpx


COURSE_PAGE = (
    "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/"
    "resources/lecture-1-the-geometry-of-linear-equations/"
)
LICENSE_PAGE = "https://ocw.mit.edu/pages/privacy-and-terms-of-use/"
CONTENT_TYPES = [
    "outline",
    "daily_records",
    "ai_reviews",
    "exercises",
    "mistakes",
    "notes",
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class Flow:
    def __init__(self, base_url: str, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.raw_dir = output_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(900, connect=30),
            trust_env=False,
        )
        self.timings: dict[str, float] = {}

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
        if response.status_code == 204:
            return None
        return response.json()

    def step(self, name: str, action: Callable[[], Any]) -> Any:
        result_path = self.raw_dir / f"{name}.json"
        if result_path.exists():
            saved = json.loads(result_path.read_text(encoding="utf-8"))
            self.timings[name] = float(saved.get("elapsed_seconds", 0))
            return saved["data"]
        started = time.perf_counter()
        try:
            data = action()
        except Exception as error:
            write_json(self.raw_dir / f"{name}.error.json", {"error": str(error)})
            raise
        elapsed = round(time.perf_counter() - started, 3)
        self.timings[name] = elapsed
        write_json(result_path, {"elapsed_seconds": elapsed, "data": data})
        print(f"{name}: {elapsed:.1f}s", flush=True)
        return data

    def optional_step(self, name: str, action: Callable[[], Any]) -> Any | None:
        try:
            return self.step(name, action)
        except Exception as error:
            print(f"{name}: BLOCKED - {error}", flush=True)
            return None

    def close(self) -> None:
        write_json(self.output_dir / "timings.json", self.timings)
        self.client.close()


def complete_node(flow: Flow, record: dict[str, Any], node_key: str) -> None:
    node = next(item for item in record["workflow_nodes"] if item["node_key"] == node_key)
    flow.step(
        f"node-{node_key}",
        lambda: flow.request(
            "PATCH",
            f"/api/workflow-nodes/{node['id']}",
            json={"status": "completed"},
        ),
    )


def upload_pdf(
    flow: Flow,
    pdf_path: Path,
    course_id: int,
    chapter_id: int,
    section_id: int,
) -> dict[str, Any]:
    def upload() -> Any:
        with pdf_path.open("rb") as source:
            return flow.request(
                "POST",
                "/api/materials/pdf",
                data={
                    "title": "MIT 18.06 Lecture 1 transcript",
                    "course_id": str(course_id),
                    "chapter_id": str(chapter_id),
                    "section_id": str(section_id),
                    "is_primary": "false",
                },
                files={"file": (pdf_path.name, source, "application/pdf")},
            )

    return flow.step("material-pdf", upload)


def exercise_answer_keys(database_path: Path) -> dict[int, dict[str, Any]]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT id, answer_key_json FROM exercise_items ORDER BY position"
        ).fetchall()
    return {item_id: json.loads(value) for item_id, value in rows}


def answer_exercise(
    flow: Flow,
    exercise: dict[str, Any],
    answer_keys: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    for item in exercise["items"]:
        answer_key = answer_keys[item["id"]]
        if item["item_type"] in {"single_choice", "multiple_choice"}:
            selected = list(answer_key["selected_options"])
            if item["position"] == 2:
                selected = [
                    option["id"]
                    for option in item["options"]
                    if option["id"] not in selected
                ][:1]
            answer = ""
        else:
            selected = []
            answer = answer_key["answer_markdown"]
            if item["position"] == 10:
                answer = (
                    "因为 $A$ 是方阵，所以它的列向量一定线性无关，"
                    "任意 $b$ 都能写成这些列向量的唯一线性组合。"
                )
        flow.request(
            "PUT",
            f"/api/exercise-items/{item['id']}/response",
            json={"answer_markdown": answer, "selected_options": selected},
        )
    return flow.request("POST", f"/api/exercises/{exercise['id']}/complete")


def build_checks(
    materials: list[dict[str, Any]],
    exercise: dict[str, Any],
    graded: dict[str, Any],
    preview: dict[str, Any],
    completed: dict[str, Any],
    note: dict[str, Any],
    next_record: dict[str, Any],
) -> dict[str, Any]:
    items = exercise["items"]
    verdicts = [item["response"]["verdict"] for item in graded["items"]]
    questions = [preview[f"question_{position}"] for position in range(1, 4)]
    checks = {
        "materials_ready": len(materials) == 2
        and all(item["status"] == "ready" for item in materials),
        "multiple_material_types": {item["source_type"] for item in materials}
        >= {"url", "pdf"},
        "practice_has_12_items": len(items) == 12,
        "practice_has_4_choices": sum(
            item["item_type"] in {"single_choice", "multiple_choice"} for item in items
        )
        == 4,
        "practice_positions_complete": [item["position"] for item in items]
        == list(range(1, 13)),
        "grading_complete": len(verdicts) == 12 and all(verdicts),
        "grading_found_deliberate_errors": any(value != "correct" for value in verdicts),
        "preview_has_3_questions": len(questions) == 3 and all(value.strip() for value in questions),
        "daily_summary_present": len(completed["context_summary"].strip()) >= 80,
        "note_is_detailed": len(note["text"].strip()) >= 2500,
        "note_uses_markdown": "## " in note["text"] and "$" in note["text"],
        "next_day_received_questions": next_record["previous_preview_questions"] is not None,
    }
    return {"checks": checks, "all_passed": all(checks.values()), "verdicts": verdicts}


def run(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    vault = output_dir / "obsidian-vault"
    vault.mkdir(parents=True, exist_ok=True)
    flow = Flow(args.base_url, output_dir)
    try:
        flow.step("health", lambda: flow.request("GET", "/api/health"))
        flow.step("providers", lambda: flow.request("GET", "/api/ai/providers"))
        flow.step(
            "vault",
            lambda: flow.request(
                "PUT", "/api/settings/obsidian", json={"obsidian_vault_path": str(vault)}
            ),
        )
        flow.step(
            "learner-profile",
            lambda: flow.request(
                "PUT",
                "/api/settings/learner-profile",
                json={
                    "learner_profile": (
                        "我是一名工科研究生，学过高等数学、线性代数、机器学习和"
                        "深度学习基础，有一定编程能力。"
                    )
                },
            ),
        )
        course = flow.step(
            "course",
            lambda: flow.request(
                "POST",
                "/api/courses",
                json={
                    "name": "MIT 18.06 线性代数示例",
                    "description": "基于 MIT OpenCourseWare 真实材料的 Lumina 全流程示例。",
                    "learning_goal": "理解线性方程组的行图像、列图像与矩阵表示。",
                },
            ),
        )
        chapter = flow.step(
            "chapter",
            lambda: flow.request(
                "POST", f"/api/courses/{course['id']}/chapters", json={"title": "第一章 线性方程"}
            ),
        )
        section = flow.step(
            "section",
            lambda: flow.request(
                "POST",
                f"/api/chapters/{chapter['id']}/sections",
                json={"title": "第一讲 线性方程的几何图像"},
            ),
        )
        flow.step(
            "material-url",
            lambda: flow.request(
                "POST",
                "/api/materials/url",
                json={
                    "title": "MIT OCW Lecture 1 course page",
                    "url": COURSE_PAGE,
                    "course_id": course["id"],
                    "chapter_id": chapter["id"],
                    "section_id": section["id"],
                    "is_primary": False,
                },
            ),
        )
        upload_pdf(flow, args.pdf, course["id"], chapter["id"], section["id"])
        record = flow.step(
            "record-day-1",
            lambda: flow.request(
                "POST", f"/api/sections/{section['id']}/daily-records/today"
            ),
        )
        for material in record["materials"]:
            flow.step(
                f"material-scope-{material['id']}",
                lambda material=material: flow.request(
                    "PUT",
                    f"/api/daily-records/{record['id']}/materials/{material['id']}",
                    json={
                        "selected": True,
                        "range_note": (
                            "Lecture 1 全文；重点关注 row picture、column picture 和 Ax=b"
                        ),
                    },
                ),
            )
        record = flow.step(
            "record-filled",
            lambda: flow.request(
                "PATCH",
                f"/api/daily-records/{record['id']}",
                json={
                    "recall_last_learned": "此前学习过矩阵乘法和二元一次方程组。",
                    "recall_core_concepts": (
                        "我记得 $Ax=b$ 表示矩阵与向量相乘，但容易把矩阵运算和几何图像"
                        "分开理解。"
                    ),
                    "recall_clear_parts": "能够代入检验二元方程组的解，也能进行基础消元。",
                    "recall_blocked_parts": (
                        "不清楚行图像、列图像为何描述同一个系统，也误以为方阵一定唯一可解。"
                    ),
                    "study_material_scope": (
                        "完整学习 MIT OCW Lecture 1 课程页和官方 PDF 逐字稿，重点理解三种视角。"
                    ),
                    "reconstruct_problem": (
                        "本讲要解决如何从几何、向量组合和矩阵三个层面理解线性方程组。"
                    ),
                    "reconstruct_main_learning": (
                        "行图像寻找各方程几何对象的公共交点；列图像判断列向量组合是否能"
                        "得到 $b$；矩阵形式用 $Ax=b$ 统一表达。"
                    ),
                    "reconstruct_math": (
                        "对于 $2x-y=0$、$-x+2y=3$，解为 $(1,2)$。一般地，"
                        "$Ax=b$ 可解当且仅当 $b\\in C(A)$。"
                    ),
                },
            ),
        )
        flow.step(
            "recall-review",
            lambda: flow.request(
                "POST", f"/api/daily-records/{record['id']}/ai-review/recall_review"
            ),
        )
        complete_node(flow, record, "recall")
        complete_node(flow, record, "study")
        flow.step(
            "reconstruction-review",
            lambda: flow.request(
                "POST",
                f"/api/daily-records/{record['id']}/ai-review/reconstruction_review",
            ),
        )
        complete_node(flow, record, "reconstruct")
        exercise = flow.step(
            "practice",
            lambda: flow.request("POST", f"/api/daily-records/{record['id']}/ai-practice"),
        )
        answer_keys = exercise_answer_keys(output_dir / "qa.db")
        flow.step("answers", lambda: answer_exercise(flow, exercise, answer_keys))
        graded = flow.step(
            "grading",
            lambda: flow.request("POST", f"/api/exercises/{exercise['id']}/ai-grade"),
        )
        wrong = next(
            item for item in graded["items"] if item["response"]["verdict"] != "correct"
        )
        flow.step(
            "mistake",
            lambda: flow.request(
                "POST",
                f"/api/exercises/{exercise['id']}/mistakes",
                json={
                    "exercise_item_id": wrong["id"],
                    "original_question": wrong["stem_markdown"],
                    "user_answer": wrong["response"]["answer_markdown"]
                    or ", ".join(wrong["response"]["selected_options"]),
                    "error_content": wrong["response"]["feedback_markdown"],
                    "error_type": "concept",
                    "correct_approach": "先判断主元、零空间和 $b$ 是否属于列空间。",
                    "cause_analysis": "把方阵误当成可逆矩阵，没有检查列向量是否线性无关。",
                },
            ),
        )
        preview = flow.step(
            "preview",
            lambda: flow.request(
                "POST", f"/api/daily-records/{record['id']}/ai-preview-questions"
            ),
        )
        completed = flow.step(
            "daily-complete",
            lambda: flow.request("POST", f"/api/daily-records/{record['id']}/complete"),
        )
        existing = """# 第一讲 线性方程的几何图像

我的原始记录：行图像看约束的交，列图像看列向量如何组合成 $b$，二者由 $Ax=b$ 统一。
"""
        draft = flow.step(
            "note-draft",
            lambda: flow.request(
                "POST",
                f"/api/daily-records/{record['id']}/ai-section-note",
                json={"existing_content": existing, "mode": "revise"},
            ),
        )
        polished = flow.optional_step(
            "note-polished",
            lambda: flow.request(
                "POST",
                f"/api/sections/{section['id']}/ai-polish-note",
                json={
                    "content": draft["text"],
                    "context": (
                        "保留 MIT Lecture 1 的材料依据、数学公式和原始记录，"
                        "只做中文表达与 Obsidian Markdown 润色。"
                    ),
                },
            ),
        )
        note = polished or draft
        flow.step(
            "note-saved",
            lambda: flow.request(
                "PUT",
                f"/api/sections/{section['id']}/note",
                json={
                    "content": note["text"],
                    "expected_modified_at_ns": None,
                    "force_overwrite": False,
                },
            ),
        )
        flow.step(
            "section-complete",
            lambda: flow.request(
                "PATCH", f"/api/sections/{section['id']}", json={"status": "completed"}
            ),
        )
        (output_dir / "today.txt").write_text("2026-07-23\n", encoding="utf-8")
        next_record = flow.step(
            "record-day-2",
            lambda: flow.request(
                "POST",
                f"/api/sections/{section['id']}/daily-records/today?continue_completed=true",
            ),
        )
        flow.step(
            "next-recall-prompt",
            lambda: flow.request(
                "POST", f"/api/daily-records/{next_record['id']}/ai-prompts/recall_review"
            ),
        )
        final_record = flow.step(
            "final-record",
            lambda: flow.request("GET", f"/api/daily-records/{record['id']}"),
        )
        materials = flow.step("final-materials", lambda: flow.request("GET", "/api/materials"))
        checks = build_checks(
            materials, exercise, graded, preview, completed, note, next_record
        )
        final_providers = flow.step(
            "providers-final", lambda: flow.request("GET", "/api/ai/providers")
        )
        checks["providers"] = final_providers
        checks["gemini_polish_completed"] = polished is not None
        checks["source_reference_count"] = len(final_record["ai_source_refs"])
        checks["source_pages"] = [COURSE_PAGE, LICENSE_PAGE]
        write_json(output_dir / "acceptance-summary.json", checks)

        export_response = flow.client.post(
            "/api/export/archive",
            json={"course_ids": [course["id"]], "content_types": CONTENT_TYPES},
        )
        export_response.raise_for_status()
        export_path = output_dir / "example-export.zip"
        export_path.write_bytes(export_response.content)
        with zipfile.ZipFile(export_path) as archive:
            write_json(output_dir / "export-files.json", archive.namelist())
    finally:
        flow.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the isolated Lumina real-material flow")
    parser.add_argument("--base-url", default="http://127.0.0.1:8013")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    return args


if __name__ == "__main__":
    run(parse_args())
