from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AiInteraction,
    Chapter,
    Course,
    DailyRecord,
    Exercise,
    Section,
    WorkflowNodeState,
)


def test_course_to_today_record_crud_flow(client: TestClient, app: FastAPI) -> None:
    assert client.get("/api/courses").json() == []
    assert client.post("/api/courses", json={"name": "   "}).status_code == 422

    response = client.post(
        "/api/courses",
        json={
            "name": "概率论",
            "description": "课程描述",
            "learning_goal": "建立概率建模基础",
        },
    )
    assert response.status_code == 201
    course = response.json()

    response = client.patch(
        f"/api/courses/{course['id']}",
        json={"name": "概率论与数理统计"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "概率论与数理统计"

    first_chapter = client.post(
        f"/api/courses/{course['id']}/chapters", json={"title": "随机事件"}
    ).json()
    second_chapter = client.post(
        f"/api/courses/{course['id']}/chapters", json={"title": "随机变量"}
    ).json()
    assert (first_chapter["position"], second_chapter["position"]) == (0, 1)

    response = client.patch(f"/api/chapters/{first_chapter['id']}", json={"title": "概率基础"})
    assert response.json()["title"] == "概率基础"

    response = client.post(
        f"/api/chapters/{first_chapter['id']}/sections",
        json={"title": "样本空间与事件"},
    )
    assert response.status_code == 201
    section = response.json()
    assert section["status"] == "not_started"

    first_open = client.post(f"/api/sections/{section['id']}/daily-records/today")
    assert first_open.status_code == 200
    record = first_open.json()
    assert len(record["workflow_nodes"]) == 6
    assert [node["position"] for node in record["workflow_nodes"]] == list(range(1, 7))
    assert [node["title"] for node in record["workflow_nodes"]] == [
        "闭卷回顾",
        "材料学习",
        "主动重构",
        "练习与推导",
        "批改与纠错",
        "今日收尾",
    ]
    assert all(node["status"] == "pending" for node in record["workflow_nodes"])

    second_open = client.post(f"/api/sections/{section['id']}/daily-records/today")
    assert second_open.json()["id"] == record["id"]

    detail = client.get(f"/api/courses/{course['id']}").json()
    assert detail["chapters"][0]["sections"][0]["status"] == "in_progress"

    response = client.patch(f"/api/sections/{section['id']}", json={"status": "completed"})
    assert response.json()["status"] == "completed"
    summary = client.get("/api/courses").json()[0]
    assert summary["total_sections"] == 1
    assert summary["completed_sections"] == 1
    assert summary["in_progress_sections"] == 0
    assert client.post(f"/api/sections/{section['id']}/daily-records/today").status_code == 409
    assert (
        client.post(
            f"/api/sections/{section['id']}/daily-records/today?continue_completed=true"
        ).json()["id"]
        == record["id"]
    )

    assert client.delete(f"/api/chapters/{second_chapter['id']}").status_code == 204
    assert client.delete(f"/api/courses/{course['id']}").status_code == 204
    assert client.get(f"/api/courses/{course['id']}").status_code == 404

    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Course)) == 0
        assert session.scalar(select(func.count()).select_from(Chapter)) == 0
        assert session.scalar(select(func.count()).select_from(Section)) == 0
        assert session.scalar(select(func.count()).select_from(DailyRecord)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowNodeState)) == 0
        assert session.scalar(select(func.count()).select_from(AiInteraction)) == 0
        assert session.scalar(select(func.count()).select_from(Exercise)) == 0


def test_missing_parents_return_not_found(client: TestClient) -> None:
    assert client.get("/api/courses/999").status_code == 404
    assert client.post("/api/courses/999/chapters", json={"title": "章节"}).status_code == 404
    assert client.post("/api/chapters/999/sections", json={"title": "小节"}).status_code == 404
    assert client.post("/api/sections/999/daily-records/today").status_code == 404


def test_course_list_prioritizes_recent_activity_and_places_completed_last(
    client: TestClient, app: FastAPI
) -> None:
    course_ids: dict[str, int] = {}
    record_ids: dict[str, int] = {}
    for name in ["较早学习", "最近学习", "尚未开始", "已经完成"]:
        course = client.post("/api/courses", json={"name": name}).json()
        course_ids[name] = course["id"]
        chapter = client.post(
            f"/api/courses/{course['id']}/chapters", json={"title": "第一章"}
        ).json()
        section = client.post(
            f"/api/chapters/{chapter['id']}/sections", json={"title": "第一节"}
        ).json()
        if name != "尚未开始":
            record = client.post(f"/api/sections/{section['id']}/daily-records/today").json()
            record_ids[name] = record["id"]

    now = datetime.now(UTC)
    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        session.get(DailyRecord, record_ids["较早学习"]).updated_at = now - timedelta(days=3)
        session.get(DailyRecord, record_ids["最近学习"]).updated_at = now - timedelta(hours=1)
        completed = session.get(Course, course_ids["已经完成"])
        completed.completed_at = now - timedelta(days=1)
        session.commit()

    courses = client.get("/api/courses").json()
    assert [course["name"] for course in courses] == [
        "最近学习",
        "较早学习",
        "尚未开始",
        "已经完成",
    ]
    assert [course["course_state"] for course in courses] == [
        "active",
        "active",
        "not_started",
        "completed",
    ]
    assert courses[0]["last_study_at"] is not None
    assert courses[2]["last_study_at"] is None
    assert all(course["created_at"] for course in courses)
    assert all(
        datetime.fromisoformat(course["created_at"].replace("Z", "+00:00")).tzinfo == UTC
        for course in courses
    )
