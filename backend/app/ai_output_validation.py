from collections.abc import Callable
from typing import Any

from app.ai_providers import AiProviderError


class AiOutputValidationError(AiProviderError):
    pass


def validate_practice_output(payload: dict[str, Any]) -> None:
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

    return validate


def validate_preview_output(payload: dict[str, Any]) -> None:
    questions = payload.get("questions")
    if (
        not isinstance(questions, list)
        or len(questions) != 3
        or not all(isinstance(question, str) and question.strip() for question in questions)
    ):
        raise AiOutputValidationError("预习问题生成结果不是完整的 3 个问题")
