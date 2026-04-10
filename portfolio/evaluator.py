"""Call 1: 10-criteria portfolio evaluation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from portfolio.llm import call_multimodal
from portfolio.parser import ParsedPortfolio
from portfolio.prompts import EVALUATION_SCHEMA, SYSTEM_PROMPT_EVALUATOR


class EvaluatorError(Exception):
    """Raised when LLM response cannot be parsed into a valid EvaluationResult."""


@dataclass
class EvaluationResult:
    overall: dict
    criteria: list[dict]
    model_used: str
    tokens: dict


def _validate(data: dict) -> None:
    if "overall" not in data or "criteria" not in data:
        raise EvaluatorError("missing 'overall' or 'criteria'")
    overall = data["overall"]
    for k in ("one_liner", "strengths", "weaknesses"):
        if k not in overall:
            raise EvaluatorError(f"overall missing '{k}'")
    if not isinstance(data["criteria"], list) or len(data["criteria"]) != 10:
        got = len(data["criteria"]) if isinstance(data["criteria"], list) else "non-list"
        raise EvaluatorError(f"'criteria' must have exactly 10 items, got {got}")
    for c in data["criteria"]:
        for k in ("id", "title", "score", "evaluation", "evidence"):
            if k not in c:
                raise EvaluatorError(f"criterion missing '{k}'")
        score = c["score"]
        if not isinstance(score, int) or not (1 <= score <= 5):
            raise EvaluatorError(
                f"criterion {c.get('id')} score must be int 1-5, got {score!r}"
            )


def evaluate(
    parsed: ParsedPortfolio,
    api_key: str | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> EvaluationResult:
    """Run Call 1: produce a 10-criteria evaluation.

    Raises:
        EvaluatorError: if the LLM response is malformed.
        LLMUnavailableError: if the LLM call fails entirely.
    """
    user_text = (
        "다음은 SW마에스트로 연수생의 포트폴리오 마크다운입니다. "
        "10가지 기준에 따라 평가해주세요.\n\n---\n\n"
        + parsed.markdown
    )

    text, model_used, tokens = call_multimodal(
        system_prompt=SYSTEM_PROMPT_EVALUATOR,
        user_text=user_text,
        images=parsed.images,
        response_schema=EVALUATION_SCHEMA,
        api_key=api_key,
        status_callback=status_callback,
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise EvaluatorError(f"LLM did not return valid JSON: {e}") from e

    _validate(data)

    return EvaluationResult(
        overall=data["overall"],
        criteria=data["criteria"],
        model_used=model_used,
        tokens=tokens,
    )
