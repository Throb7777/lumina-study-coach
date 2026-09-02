import pytest

from app.ai_output_validation import (
    AiOutputValidationError,
    validate_practice_output,
    validate_preview_output,
)


def practice_payload() -> dict:
    return {
        "items": [
            {
                "position": position,
                "item_type": "single_choice" if position <= 4 else "short_answer",
                "stem_markdown": f"请分析第 {position} 个给定案例中的明确条件与结论。",
            }
            for position in range(1, 13)
        ]
    }


def test_practice_validation_accepts_distinct_specific_questions() -> None:
    validate_practice_output(practice_payload())


def test_practice_validation_rejects_generic_delegated_scenario() -> None:
    payload = practice_payload()
    payload["items"][6]["stem_markdown"] = (
        "结合你的研究背景，选择一个交通或城市系统中的随机现象进行建模。"
    )

    with pytest.raises(AiOutputValidationError, match="不够具体"):
        validate_practice_output(payload)


def test_practice_validation_rejects_near_duplicate_history_question() -> None:
    payload = practice_payload()
    payload["items"][0]["stem_markdown"] = (
        "已知某路口一分钟到达车辆数服从参数为四的泊松分布，求恰有两辆到达的概率。"
    )
    excluded = [
        "已知某路口一分钟到达车辆数服从参数为4的泊松分布，计算恰好两辆车到达的概率。"
    ]

    with pytest.raises(AiOutputValidationError, match="重复度过高"):
        validate_practice_output(payload, excluded)


def test_preview_validation_compacts_numbered_questions_and_inline_math() -> None:
    payload = {
        "questions": [
            r"1. 说明 $\\mathrm{Cov}(X,Y)$ 的含义。",
            "2）\n\n比较独立与不相关的条件。",
            r"3. 用 $$P(A\mid B)=P(A)$$ 检查结论。",
        ]
    }

    validate_preview_output(payload)

    assert payload["questions"] == [
        r"说明 $\mathrm{Cov}(X,Y)$ 的含义。",
        "比较独立与不相关的条件。",
        r"用 $P(A\mid B)=P(A)$ 检查结论。",
    ]
