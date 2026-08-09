import json
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai_providers import AiProviderResult
from app.ai_workflows import course_context
from app.models import (
    AiProvider,
    AiRun,
    AiRunStatus,
    AiRunTask,
    DailyRecord,
    PreviewQuestionSet,
    Section,
    SectionMemory,
    SectionStatus,
)


def create_today_record(client: TestClient) -> tuple[dict, dict, dict]:
    course = client.post(
        "/api/courses",
        json={"name": "测试课程", "learning_goal": "建立长期研究能力"},
    ).json()
    chapter = client.post(f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}).json()
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "第一节"}
    ).json()
    record = client.post(f"/api/sections/{section['id']}/daily-records/today").json()
    return course, section, record


def test_lists_active_ai_runs_for_page_recovery(
    client: TestClient,
    app: FastAPI,
) -> None:
    course, section, record = create_today_record(client)
    with app.state.session_factory() as session:
        session.add(
            AiRun(
                provider=AiProvider.CODEX,
                task=AiRunTask.PRACTICE_GENERATION,
                status=AiRunStatus.RUNNING,
                course_id=course["id"],
                section_id=section["id"],
                daily_record_id=record["id"],
                context_snapshot="context",
                prompt_text="prompt",
            )
        )
        session.commit()

    response = client.get(
        f"/api/ai-runs?daily_record_id={record['id']}&active_only=true"
    )

    assert response.status_code == 200
    assert response.json()[0]["task"] == "practice_generation"
    assert response.json()[0]["status"] == "running"


class SummaryCodex:
    async def generate(
        self,
        prompt: str,
        output_schema: dict | None = None,
        **options,
    ) -> AiProviderResult:
        del prompt, output_schema, options
        memory = {
            "summary": "今日学习摘要",
            "core_concepts": ["概率公理"],
            "key_methods": [],
            "unresolved_questions": [],
            "error_patterns": [],
        }
        handoff = {
            "confirmed_points": [],
            "corrections": [],
            "key_concepts": [],
            "key_formulas": [],
            "unresolved_points": [],
            "error_patterns": [],
            "source_refs": [],
        }
        return AiProviderResult(
            text=json.dumps(
                {
                    "display_markdown": "今日学习摘要",
                    "handoff": handoff,
                    "section_memory": memory,
                    "chapter_memory": memory,
                },
                ensure_ascii=False,
            )
        )


class SummaryService:
    def __init__(self) -> None:
        self.codex = SummaryCodex()

    async def close(self) -> None:
        return None


def test_context_uses_only_completed_preceding_sections_and_previous_preview(
    client: TestClient,
    app: FastAPI,
) -> None:
    course = client.post("/api/courses", json={"name": "上下文课程"}).json()
    chapter = client.post(
        f"/api/courses/{course['id']}/chapters", json={"title": "目标章节"}
    ).json()
    previous = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "前置小节"}
    ).json()
    current = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "当前小节"}
    ).json()
    later = client.post(
        f"/api/chapters/{chapter['id']}/sections", json={"title": "后续小节"}
    ).json()
    current_record = client.post(f"/api/sections/{current['id']}/daily-records/today").json()

    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        session.get(Section, previous["id"]).status = SectionStatus.COMPLETED
        session.get(Section, later["id"]).status = SectionStatus.COMPLETED
        session.add_all(
            [
                SectionMemory(section_id=previous["id"], summary="应当进入上下文"),
                SectionMemory(section_id=later["id"], summary="不应进入上下文"),
            ]
        )
        older = DailyRecord(
            section_id=current["id"],
            study_date=date.today() - timedelta(days=1),
            context_summary="昨天已经掌握条件定义",
            is_completed=True,
        )
        older.preview_question_set = PreviewQuestionSet(
            prompt_text="preview",
            question_1="问题一",
            question_2="问题二",
            question_3="问题三",
        )
        session.add(older)
        session.commit()

        record = session.get(DailyRecord, current_record["id"])
        context = course_context(session, record, AiRunTask.PRACTICE_GENERATION)
        assert "章节：目标章节" in context
        assert "前置小节：应当进入上下文" in context
        assert "后续小节" not in context
        assert "昨天已经掌握条件定义" in context
        assert "问题一" in context


def test_learning_content_node_progress_and_history(client: TestClient, app: FastAPI) -> None:
    app.state.ai_service = SummaryService()
    course, section, record = create_today_record(client)
    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        session.add(
            DailyRecord(
                section_id=section["id"],
                study_date=date.today() - timedelta(days=1),
                recall_last_learned="条件概率",
                recall_core_concepts="条件概率与独立性",
                reconstruct_main_learning="贝叶斯公式",
            )
        )
        session.commit()

    response = client.patch(
        f"/api/daily-records/{record['id']}",
        json={
            "recall_last_learned": "随机事件",
            "recall_core_concepts": "样本空间",
            "recall_clear_parts": "能解释事件运算",
            "recall_blocked_parts": "条件概率",
            "study_material_scope": "教材第 1.2 节",
            "reconstruct_problem": "描述不确定事件",
            "reconstruct_main_learning": "概率公理",
            "reconstruct_math": "P(A) >= 0",
            "reconstruct_explanation": "可以用自己的语言解释",
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["study_material_scope"] == "教材第 1.2 节"
    assert updated["previous_records"][0]["recall_last_learned"] == "条件概率"

    nodes = {node["node_key"]: node for node in updated["workflow_nodes"]}
    assert (
        client.patch(
            f"/api/workflow-nodes/{nodes['recall']['id']}", json={"status": "completed"}
        ).json()["status"]
        == "completed"
    )
    assert (
        client.patch(
            f"/api/workflow-nodes/{nodes['recall']['id']}", json={"status": "skipped"}
        ).status_code
        == 422
    )
    practice_url = f"/api/workflow-nodes/{nodes['practice']['id']}"
    assert client.patch(practice_url, json={"status": "skipped"}).status_code == 409
    assert (
        client.patch(f"{practice_url}?confirm_skip=true", json={"status": "skipped"}).json()[
            "status"
        ]
        == "skipped"
    )
    assert (
        client.patch(
            f"/api/workflow-nodes/{nodes['daily_close']['id']}",
            json={"status": "completed"},
        ).status_code
        == 422
    )

    completed = client.post(f"/api/daily-records/{record['id']}/complete").json()
    assert completed["is_completed"] is True
    assert (
        next(node for node in completed["workflow_nodes"] if node["node_key"] == "daily_close")[
            "status"
        ]
        == "completed"
    )

    course_detail = client.get(f"/api/courses/{course['id']}").json()
    history = course_detail["chapters"][0]["sections"][0]["daily_records"]
    assert [item["study_date"] for item in history] == sorted(
        [item["study_date"] for item in history], reverse=True
    )


def test_ai_prompts_exercise_and_grading_flow(client: TestClient) -> None:
    _, _, record = create_today_record(client)
    record_id = record["id"]
    client.patch(
        f"/api/daily-records/{record_id}",
        json={
            "recall_last_learned": "样本空间",
            "recall_blocked_parts": "该字段不应进入提示词",
            "reconstruct_main_learning": "概率公理",
            "study_material_scope": "教材第 1 章",
        },
    )

    recall = client.post(f"/api/daily-records/{record_id}/ai-prompts/recall_review")
    assert recall.status_code == 201
    assert "章节：第一章" in recall.json()["prompt_text"]
    assert "小节：第一节" in recall.json()["prompt_text"]
    assert "建立长期研究能力" in recall.json()["prompt_text"]
    assert "该字段不应进入提示词" not in recall.json()["prompt_text"]
    response = client.patch(
        f"/api/ai-interactions/{recall.json()['id']}",
        json={"feedback_text": "回忆基本准确"},
    )
    assert response.json()["feedback_text"] == "回忆基本准确"

    reconstruction = client.post(f"/api/daily-records/{record_id}/ai-prompts/reconstruction_review")
    assert reconstruction.status_code == 201
    assert "概率公理" in reconstruction.json()["prompt_text"]
    assert "该字段不应进入提示词" not in reconstruction.json()["prompt_text"]

    exercise = client.post(f"/api/daily-records/{record_id}/exercises")
    assert exercise.status_code == 201
    exercise_body = exercise.json()
    assert "生成恰好 12 道题" in exercise_body["generation_prompt"]
    assert "恰好 4 道选择题" in exercise_body["generation_prompt"]
    assert client.post(f"/api/exercises/{exercise_body['id']}/grading-prompt").status_code == 422

    response = client.patch(
        f"/api/exercises/{exercise_body['id']}",
        json={"ai_questions": "1. 定义概率空间", "user_answers": "概率空间由三部分组成"},
    )
    assert response.status_code == 200
    response = client.post(f"/api/exercises/{exercise_body['id']}/grading-prompt")
    assert "1. 定义概率空间" in response.json()["grading_prompt"]
    response = client.patch(
        f"/api/exercises/{exercise_body['id']}",
        json={"ai_feedback": "答案部分正确"},
    )
    assert response.json()["ai_feedback"] == "答案部分正确"

    refreshed = client.get(f"/api/daily-records/{record_id}").json()
    assert len(refreshed["ai_interactions"]) == 2
    assert len(refreshed["exercises"]) == 1


def test_structured_mistake_crud(client: TestClient) -> None:
    _, _, record = create_today_record(client)
    exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    payload = {
        "original_question": "何时可以使用贝叶斯公式？",
        "user_answer": "任何条件下都可以。",
        "error_content": "忽略了条件概率分母必须非零。",
        "error_type": "formula_condition",
        "correct_approach": "先确认条件事件概率非零，再应用公式。",
        "cause_analysis": "没有理解公式成立的前提。",
    }

    response = client.post(f"/api/exercises/{exercise['id']}/mistakes", json=payload)
    assert response.status_code == 201
    mistake = response.json()
    assert mistake["status"] == "unresolved"
    assert mistake["error_type"] == "formula_condition"

    response = client.patch(
        f"/api/mistakes/{mistake['id']}",
        json={"status": "understood", "cause_analysis": "现在能说明适用条件。"},
    )
    assert response.json()["status"] == "understood"

    refreshed = client.get(f"/api/daily-records/{record['id']}").json()
    assert refreshed["exercises"][0]["mistakes"][0]["cause_analysis"] == ("现在能说明适用条件。")

    assert client.delete(f"/api/mistakes/{mistake['id']}").status_code == 204
    assert client.patch(f"/api/mistakes/{mistake['id']}", json={}).status_code == 404
    assert client.post("/api/exercises/999/mistakes", json=payload).status_code == 404


def test_legacy_exercise_can_be_deleted_with_related_mistakes(client: TestClient) -> None:
    _, _, record = create_today_record(client)
    exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
    mistake = client.post(
        f"/api/exercises/{exercise['id']}/mistakes",
        json={
            "original_question": "旧版题目",
            "user_answer": "旧版答案",
            "error_content": "旧版错误",
            "error_type": "concept",
            "correct_approach": "正确思路",
            "cause_analysis": "理解不完整",
        },
    )
    assert mistake.status_code == 201

    assert client.delete(f"/api/exercises/{exercise['id']}").status_code == 204
    assert client.get(f"/api/daily-records/{record['id']}").json()["exercises"] == []
    assert client.delete(f"/api/exercises/{exercise['id']}").status_code == 404


def test_preview_questions_are_read_only_handoff_to_next_course_record(
    client: TestClient, app: FastAPI
) -> None:
    current_day = [date(2026, 7, 20)]
    app.state.today_provider = lambda: current_day[0]
    _, section, record = create_today_record(client)
    client.patch(
        f"/api/daily-records/{record['id']}",
        json={
            "study_material_scope": "教材第 2 章",
            "reconstruct_main_learning": "全概率公式与贝叶斯公式",
            "reconstruct_math": "P(A|B)=P(B|A)P(A)/P(B)",
        },
    )

    response = client.post(f"/api/daily-records/{record['id']}/preview-questions/prompt")
    assert response.status_code == 200
    assert "恰好 3 条" in response.json()["prompt_text"]
    assert "全概率公式与贝叶斯公式" in response.json()["prompt_text"]

    assert (
        client.put(
            f"/api/daily-records/{record['id']}/preview-questions",
            json={"question_1": "问题一", "question_2": "问题二", "question_3": "   "},
        ).status_code
        == 422
    )
    questions = {
        "question_1": "公式 $P(\\omega)=1$ 为什么必须归一化？",
        "question_2": "分母为零时为什么不能使用条件概率？",
        "question_3": "如何把公式用于一次实际判断？",
    }
    stored_questions = {**questions, "question_1": "公式 $P(\x07omega)=1$ 为什么必须归一化？"}
    response = client.put(
        f"/api/daily-records/{record['id']}/preview-questions",
        json=stored_questions,
    )
    assert response.status_code == 200
    assert response.json()["question_2"] == questions["question_2"]

    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        stored_record = session.get(DailyRecord, record["id"])
        stored_record.is_completed = True
        session.commit()

    next_section = client.post(
        f"/api/chapters/{section['chapter_id']}/sections",
        json={"title": "第二节"},
    ).json()

    current_day[0] += timedelta(days=1)
    next_record = client.post(
        f"/api/sections/{next_section['id']}/daily-records/today"
    ).json()
    assert next_record["id"] != record["id"]
    assert next_record["previous_preview_questions"] == {
        "daily_record_id": record["id"],
        "section_id": section["id"],
        "section_title": section["title"],
        "study_date": "2026-07-20",
        "questions": list(questions.values()),
    }
    carried_reflection = next_record["guided_reflections"][0]
    assert carried_reflection["kind"] == "recall"
    assert [item["question_markdown"] for item in carried_reflection["questions"]] == list(
        questions.values()
    )
    prompt = client.post(
        f"/api/daily-records/{next_record['id']}/ai-prompts/recall_review"
    ).json()["prompt_text"]
    assert questions["question_1"] in prompt


def test_recall_handoff_does_not_skip_latest_completed_record_without_questions(
    client: TestClient,
    app: FastAPI,
) -> None:
    course = client.post("/api/courses", json={"name": "严格顺序课程"}).json()
    chapter = client.post(
        f"/api/courses/{course['id']}/chapters",
        json={"title": "第一章"},
    ).json()
    first_section = client.post(
        f"/api/chapters/{chapter['id']}/sections",
        json={"title": "第一节"},
    ).json()
    second_section = client.post(
        f"/api/chapters/{chapter['id']}/sections",
        json={"title": "第二节"},
    ).json()
    third_section = client.post(
        f"/api/chapters/{chapter['id']}/sections",
        json={"title": "第三节"},
    ).json()
    first_record = client.post(
        f"/api/sections/{first_section['id']}/daily-records/today"
    ).json()
    client.post(f"/api/daily-records/{first_record['id']}/preview-questions/prompt")
    client.put(
        f"/api/daily-records/{first_record['id']}/preview-questions",
        json={"question_1": "旧问题一", "question_2": "旧问题二", "question_3": "旧问题三"},
    )
    second_record = client.post(
        f"/api/sections/{second_section['id']}/daily-records/today"
    ).json()

    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        session.get(DailyRecord, first_record["id"]).is_completed = True
        session.get(DailyRecord, second_record["id"]).is_completed = True
        session.commit()

    third_record = client.post(
        f"/api/sections/{third_section['id']}/daily-records/today"
    ).json()

    assert third_record["previous_preview_questions"] == {
        "daily_record_id": second_record["id"],
        "section_id": second_section["id"],
        "section_title": "第二节",
        "study_date": second_record["study_date"],
        "questions": [],
    }
    assert third_record["guided_reflections"] == []


def test_learning_flow_missing_resources(client: TestClient) -> None:
    assert client.patch("/api/daily-records/999", json={}).status_code == 404
    assert client.patch("/api/workflow-nodes/999", json={"status": "completed"}).status_code == 404
    assert client.post("/api/daily-records/999/complete").status_code == 404
    assert client.patch("/api/ai-interactions/999", json={"feedback_text": "x"}).status_code == 404
    assert client.patch("/api/exercises/999", json={"user_answers": "x"}).status_code == 404
