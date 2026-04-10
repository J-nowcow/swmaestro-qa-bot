"""Unit tests for portfolio.evaluator — mocks portfolio.llm.call_multimodal."""
import json
from unittest.mock import patch

import pytest

from portfolio.evaluator import EvaluationResult, EvaluatorError, evaluate
from portfolio.parser import ParsedPortfolio, PortfolioStats


def _parsed() -> ParsedPortfolio:
    return ParsedPortfolio(
        markdown="# About\nI build things.",
        images=[],
        stats=PortfolioStats(page_count=1, image_count=0, image_truncated=False, total_chars=20),
    )


def _valid_json() -> str:
    return json.dumps(
        {
            "overall": {
                "one_liner": "OK",
                "strengths": ["a", "b", "c"],
                "weaknesses": ["x", "y", "z"],
            },
            "criteria": [
                {"id": i, "title": f"기준 {i}", "score": 3, "evaluation": "e", "evidence": "ev"}
                for i in range(1, 11)
            ],
        }
    )


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_returns_parsed_result(mock_call):
    mock_call.return_value = (_valid_json(), "gemini-2.5-flash", {"input": 100, "output": 50})

    result = evaluate(_parsed())

    assert isinstance(result, EvaluationResult)
    assert result.model_used == "gemini-2.5-flash"
    assert result.tokens == {"input": 100, "output": 50}
    assert result.overall["one_liner"] == "OK"
    assert len(result.criteria) == 10


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_passes_images_to_llm(mock_call):
    mock_call.return_value = (_valid_json(), "gemini-2.5-flash", {"input": 0, "output": 0})

    parsed = _parsed()
    evaluate(parsed)

    kwargs = mock_call.call_args.kwargs
    assert kwargs["images"] is parsed.images


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_invalid_json_raises(mock_call):
    mock_call.return_value = ("not json", "gemini-2.5-flash", {})

    with pytest.raises(EvaluatorError):
        evaluate(_parsed())


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_missing_required_field_raises(mock_call):
    mock_call.return_value = (json.dumps({"overall": {}}), "gemini-2.5-flash", {})

    with pytest.raises(EvaluatorError):
        evaluate(_parsed())


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_passes_byok_key(mock_call):
    mock_call.return_value = (_valid_json(), "gemini-2.5-flash", {})

    evaluate(_parsed(), api_key="byok-test")

    assert mock_call.call_args.kwargs["api_key"] == "byok-test"


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_wrong_criteria_count_raises(mock_call):
    """criteria with !=10 items must be rejected."""
    payload = json.dumps(
        {
            "overall": {"one_liner": "ok", "strengths": ["a"], "weaknesses": ["b"]},
            "criteria": [
                {"id": i, "title": f"k{i}", "score": 3, "evaluation": "e", "evidence": "ev"}
                for i in range(1, 10)  # only 9 items
            ],
        }
    )
    mock_call.return_value = (payload, "gemini-2.5-flash", {})
    with pytest.raises(EvaluatorError, match="exactly 10"):
        evaluate(_parsed())


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_score_out_of_range_raises(mock_call):
    """score outside 1..5 must be rejected."""
    criteria = [
        {"id": i, "title": f"k{i}", "score": 3, "evaluation": "e", "evidence": "ev"}
        for i in range(1, 11)
    ]
    criteria[0]["score"] = 7  # invalid
    payload = json.dumps(
        {
            "overall": {"one_liner": "ok", "strengths": ["a"], "weaknesses": ["b"]},
            "criteria": criteria,
        }
    )
    mock_call.return_value = (payload, "gemini-2.5-flash", {})
    with pytest.raises(EvaluatorError, match="score"):
        evaluate(_parsed())


@patch("portfolio.evaluator.call_multimodal")
def test_evaluate_score_non_int_raises(mock_call):
    """score being a string must be rejected."""
    criteria = [
        {"id": i, "title": f"k{i}", "score": 3, "evaluation": "e", "evidence": "ev"}
        for i in range(1, 11)
    ]
    criteria[0]["score"] = "3"  # string instead of int
    payload = json.dumps(
        {
            "overall": {"one_liner": "ok", "strengths": ["a"], "weaknesses": ["b"]},
            "criteria": criteria,
        }
    )
    mock_call.return_value = (payload, "gemini-2.5-flash", {})
    with pytest.raises(EvaluatorError, match="score"):
        evaluate(_parsed())
