from enum import StrEnum


class WorkflowNodeKey(StrEnum):
    RECALL = "recall"
    STUDY = "study"
    RECONSTRUCT = "reconstruct"
    PRACTICE = "practice"
    REVIEW = "review"
    DAILY_CLOSE = "daily_close"
    PREVIEW_QUESTIONS = "preview_questions"
    SECTION_NOTE = "section_note"
    DAILY_COMPLETE = "daily_complete"


WORKFLOW_NODES: tuple[tuple[WorkflowNodeKey, str], ...] = (
    (WorkflowNodeKey.RECALL, "闭卷回顾"),
    (WorkflowNodeKey.STUDY, "材料学习"),
    (WorkflowNodeKey.RECONSTRUCT, "主动重构"),
    (WorkflowNodeKey.PRACTICE, "练习与推导"),
    (WorkflowNodeKey.REVIEW, "批改与纠错"),
    (WorkflowNodeKey.DAILY_CLOSE, "今日收尾"),
)

WORKFLOW_NODE_TITLES = {
    **dict(WORKFLOW_NODES),
    WorkflowNodeKey.PREVIEW_QUESTIONS: "下次回顾问题",
    WorkflowNodeKey.SECTION_NOTE: "小节笔记",
    WorkflowNodeKey.DAILY_COMPLETE: "完成今日学习",
}
