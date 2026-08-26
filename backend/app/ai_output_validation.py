import re
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any

from app.ai_providers import AiProviderError
from app.markdown import normalize_ai_markdown


class AiOutputValidationError(AiProviderError):
    pass


def validate_guided_questions_output(payload: dict[str, Any]) -> None:
    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) != 3:
        raise AiOutputValidationError("定向问题生成结果不是完整的 3 个问题")
    expected_ids = ["q1", "q2", "q3"]
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise AiOutputValidationError("定向问题生成结果格式不正确")
        if question.get("id") != expected_ids[index]:
            raise AiOutputValidationError("定向问题编号必须依次为 q1、q2、q3")
        if not str(question.get("question_markdown", "")).strip():
            raise AiOutputValidationError("定向问题内容不能为空")
        if not str(question.get("focus", "")).strip():
            raise AiOutputValidationError("定向问题检查点不能为空")


def guided_review_output_validator(
    expected_ids: list[str],
) -> Callable[[dict[str, Any]], None]:
    def validate(payload: dict[str, Any]) -> None:
        reviews = payload.get("reviews")
        if not isinstance(reviews, list) or len(reviews) != len(expected_ids):
            raise AiOutputValidationError("回顾批改没有覆盖全部问题")
        review_ids = [
            str(item.get("id", ""))
            for item in reviews
            if isinstance(item, dict)
        ]
        if review_ids != expected_ids:
            raise AiOutputValidationError("回顾批改的问题编号不完整或顺序错误")
        if any(
            not str(item.get("feedback_markdown", "")).strip()
            for item in reviews
            if isinstance(item, dict)
        ):
            raise AiOutputValidationError("回顾批改包含空反馈")

    return validate


def normalized_stem(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return "".join(character for character in normalized if character.isalnum())


def stem_similarity(left: str, right: str) -> float:
    left_normalized = normalized_stem(left)
    right_normalized = normalized_stem(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def validate_practice_output(
    payload: dict[str, Any],
    excluded_stems: list[str] | tuple[str, ...] = (),
) -> None:
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != 12:
        raise AiOutputValidationError("练习生成结果不是完整的 12 道题")
    dictionaries = [item for item in items if isinstance(item, dict)]
    choice_count = sum(
        item.get("item_type") in {"single_choice", "multiple_choice"}
        for item in dictionaries
    )
    if choice_count != 4:
        raise AiOutputValidationError("练习生成结果没有包含约定的 4 道选择题")
    positions = [item.get("position") for item in dictionaries]
    if sorted(positions) != list(range(1, 13)):
        raise AiOutputValidationError("练习生成结果的题号不完整")
    stems = [str(item.get("stem_markdown", "")).strip() for item in dictionaries]
    if any(not stem for stem in stems):
        raise AiOutputValidationError("练习生成结果包含空题干")
    generic_pattern = re.compile(
        r"(?:结合(?:你的|自身).{0,16}(?:研究|专业|工作)背景.{0,30}(?:选择|任选|自选))"
        r"|(?:(?:选择|任选|自选)一个.{0,24}(?:现象|场景|系统|案例|问题|主题))"
    )
    if any(generic_pattern.search(stem.replace("\n", "")) for stem in stems):
        raise AiOutputValidationError("练习题把关键对象交给学习者任选，题目不够具体")
    for index, stem in enumerate(stems):
        for other in stems[:index]:
            if normalized_stem(stem) == normalized_stem(other) or (
                min(len(normalized_stem(stem)), len(normalized_stem(other))) >= 24
                and stem_similarity(stem, other) >= 0.88
            ):
                raise AiOutputValidationError("同一组练习中存在重复或高度相似的题目")
        for excluded in excluded_stems:
            if normalized_stem(stem) == normalized_stem(excluded) or (
                min(len(normalized_stem(stem)), len(normalized_stem(excluded))) >= 24
                and stem_similarity(stem, excluded) >= 0.78
            ):
                raise AiOutputValidationError("练习题与材料或历史练习中的题目重复度过高")


def grading_output_validator(expected_positions: set[int]) -> Callable[[dict[str, Any]], None]:
    def validate(payload: dict[str, Any]) -> None:
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != len(expected_positions):
            raise AiOutputValidationError("批改结果没有覆盖全部题目")
        try:
            positions = {
                int(item["position"])
                for item in results
                if isinstance(item, dict)
            }
        except (KeyError, TypeError, ValueError) as error:
            raise AiOutputValidationError("批改结果题号不完整") from error
        if positions != expected_positions:
            raise AiOutputValidationError("批改结果题号不完整")
        for item in results:
            if not isinstance(item, dict):
                raise AiOutputValidationError("批改结果格式不正确")
            if item.get("verdict") not in {"correct", "partial", "incorrect"}:
                raise AiOutputValidationError("批改结果包含无效判断")
            feedback = item.get("feedback_markdown")
            if not isinstance(feedback, str) or not feedback.strip():
                raise AiOutputValidationError("批改结果包含空反馈")
            try:
                item["feedback_markdown"] = normalize_ai_markdown(feedback)
            except ValueError as error:
                raise AiOutputValidationError(str(error)) from error

    return validate


def validate_preview_output(payload: dict[str, Any]) -> None:
    questions = payload.get("questions")
    if (
        not isinstance(questions, list)
        or len(questions) != 3
        or not all(isinstance(question, str) and question.strip() for question in questions)
    ):
        raise AiOutputValidationError("下次回顾问题生成结果不是完整的 3 个问题")
