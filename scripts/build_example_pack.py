from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


COURSE_PAGE = (
    "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/"
    "resources/lecture-1-the-geometry-of-linear-equations/"
)
TRANSCRIPT_PDF = (
    "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/"
    "50702172c7cdc969615b81e6f22499fd_MIT18_06S10_L01.pdf"
)
LICENSE_PAGE = "https://ocw.mit.edu/pages/privacy-and-terms-of-use/"


def read_step(raw_dir: Path, name: str) -> dict[str, Any]:
    payload = json.loads((raw_dir / f"{name}.json").read_text(encoding="utf-8"))
    return payload["data"]


def source_labels(values: list[str]) -> list[str]:
    labels: list[str] = []
    titles = {
        1: "MIT OCW Lecture 1 course page",
        2: "MIT 18.06 Lecture 1 transcript",
    }
    for value in values:
        try:
            reference = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            continue
        material_id = int(reference.get("material_id", 0))
        positions = reference.get("chunk_positions", [])
        label = titles.get(material_id, "参考材料")
        if material_id == 1:
            label = f"{label} · 网页正文"
        elif material_id == 2 and positions:
            pages = "、".join(f"第 {position} 页" for position in positions)
            label = f"{label} · {pages}"
        if label not in labels:
            labels.append(label)
    return labels


def markdown_fields(record: dict[str, Any]) -> tuple[str, str, str]:
    recall = "\n".join(
        [
            f"- **已有知识**：{record['recall_last_learned']}",
            f"- **核心概念**：{record['recall_core_concepts']}",
            f"- **能讲清楚的部分**：{record['recall_clear_parts']}",
            f"- **当前卡点**：{record['recall_blocked_parts']}",
        ]
    )
    reconstruction = "\n".join(
        [
            f"- **要解决的问题**：{record['reconstruct_problem']}",
            f"- **主要学习内容**：{record['reconstruct_main_learning']}",
            f"- **数学定义与推导**：{record['reconstruct_math']}",
        ]
    )
    return recall, record["study_material_scope"], reconstruction


def build_pack(input_dir: Path) -> dict[str, Any]:
    raw_dir = input_dir / "raw"
    record = read_step(raw_dir, "record-filled")
    recall = read_step(raw_dir, "recall-review")
    reconstruction = read_step(raw_dir, "reconstruction-review")
    exercise = read_step(raw_dir, "grading-balanced")
    preview = read_step(raw_dir, "preview-balanced")
    completed = read_step(raw_dir, "daily-complete-balanced")
    note = read_step(raw_dir, "note-polished-balanced")
    recall_input, study_scope, reconstruction_input = markdown_fields(record)

    items = []
    for item in exercise["items"]:
        response = item["response"]
        items.append(
            {
                "position": item["position"],
                "item_type": item["item_type"],
                "difficulty": item["difficulty"],
                "stem_markdown": item["stem_markdown"],
                "options": item["options"],
                "source_refs": source_labels(item.get("source_refs", [])),
                "response": {
                    "answer_markdown": response["answer_markdown"],
                    "selected_options": response["selected_options"],
                    "verdict": response["verdict"],
                    "feedback_markdown": response["feedback_markdown"],
                },
            }
        )

    return {
        "schema_version": 1,
        "kind": "read_only_example",
        "course": {
            "name": "MIT 18.06 线性代数示例",
            "description": "用一组真实公开材料展示 Lumina 从回顾到小节笔记的完整学习闭环。",
            "learning_goal": "理解线性方程组的行图像、列图像与矩阵表示。",
            "chapter": "第一章 线性方程",
            "section": "第一讲 线性方程的几何图像",
            "study_date": record["study_date"],
        },
        "materials": [
            {
                "type": "url",
                "title": "MIT OCW Lecture 1 course page",
                "description": "课程页正文，概括 row method、column method 与 matrix method。",
                "href": COURSE_PAGE,
            },
            {
                "type": "pdf",
                "title": "MIT 18.06 Lecture 1 transcript",
                "description": "官方 PDF 逐字稿，用于核对例题、术语与材料位置。",
                "href": TRANSCRIPT_PDF,
            },
        ],
        "attribution": {
            "text": "示例材料来自 MIT OpenCourseWare，课程内容按 CC BY-NC-SA 4.0 提供。",
            "license_name": "CC BY-NC-SA 4.0",
            "license_url": LICENSE_PAGE,
        },
        "workflow": [
            {
                "number": "01",
                "key": "recall",
                "title": "知识唤醒",
                "summary": "先闭卷回忆相关知识，再由模型指出遗漏与混淆。",
                "input_markdown": recall_input,
                "feedback_markdown": recall["feedback_text"],
            },
            {
                "number": "02",
                "key": "study",
                "title": "材料学习",
                "summary": "离开 Web 自主阅读，系统保留本次材料和学习范围。",
                "input_markdown": study_scope,
                "feedback_markdown": "",
            },
            {
                "number": "03",
                "key": "reconstruct",
                "title": "主动重构",
                "summary": "合上材料，用自己的结构重新讲清问题、概念和推导。",
                "input_markdown": reconstruction_input,
                "feedback_markdown": reconstruction["feedback_text"],
            },
            {
                "number": "04",
                "key": "practice",
                "title": "练习与推导",
                "summary": "生成 12 道由浅入深的结构化练习，并逐题作答。",
                "input_markdown": "本次共 12 题，其中 4 道选择题、8 道概念/计算/应用/推导/延伸题。",
                "feedback_markdown": "",
            },
            {
                "number": "05",
                "key": "review",
                "title": "逐题复核",
                "summary": "每题分别判断正确、部分正确或错误，并给出具体修正思路。",
                "input_markdown": "10 题正确，2 题错误；错误集中在行列图像混淆和方阵可逆性的过度泛化。",
                "feedback_markdown": "",
            },
            {
                "number": "06",
                "key": "preview",
                "title": "学习收束",
                "summary": "生成今日摘要与 3 条下次思考问题，并传递到下一次学习记录。",
                "input_markdown": completed["context_summary"],
                "feedback_markdown": "",
            },
        ],
        "exercise": {"items": items},
        "preview_questions": [preview[f"question_{position}"] for position in range(1, 4)],
        "note_markdown": note["text"],
        "quality": {
            "materials": 2,
            "questions": len(items),
            "choice_questions": sum(bool(item["options"]) for item in items),
            "correct": sum(
                item["response"]["verdict"] == "correct" for item in items
            ),
            "incorrect": sum(
                item["response"]["verdict"] == "incorrect" for item in items
            ),
            "source_references": 11,
            "cross_day_handoff": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the sanitized Lumina example pack")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pack = build_pack(args.input_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
