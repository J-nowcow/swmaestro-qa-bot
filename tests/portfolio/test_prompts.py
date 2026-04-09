"""Regression tests for portfolio prompts.

These tests catch accidental removal of any of the 10 evaluation criteria
from the system prompt.
"""
from portfolio.prompts import (
    EVALUATION_SCHEMA,
    QUESTIONS_SCHEMA,
    SYSTEM_PROMPT_EVALUATOR,
    SYSTEM_PROMPT_QUESTIONS,
    TEN_CRITERIA,
)


def test_ten_criteria_count():
    assert len(TEN_CRITERIA) == 10


def test_each_criterion_has_id_and_title():
    for c in TEN_CRITERIA:
        assert "id" in c and isinstance(c["id"], int)
        assert "title" in c and c["title"]


def test_evaluator_prompt_includes_all_titles():
    for c in TEN_CRITERIA:
        assert c["title"] in SYSTEM_PROMPT_EVALUATOR, (
            f"criterion {c['id']} missing from system prompt"
        )


def test_evaluator_prompt_does_not_assume_career_path():
    """Spec: career path (취업/창업/미정) must not be assumed."""
    assert "단정하지" in SYSTEM_PROMPT_EVALUATOR or "단정 짓지" in SYSTEM_PROMPT_EVALUATOR


def test_questions_prompt_mentions_categories():
    # 5 fixed categories per spec
    for kw in ["자기소개", "기여도", "기술", "트러블", "협업"]:
        assert kw in SYSTEM_PROMPT_QUESTIONS


def test_evaluation_schema_shape():
    assert EVALUATION_SCHEMA["type"] == "object"
    props = EVALUATION_SCHEMA["properties"]
    assert "overall" in props
    assert "criteria" in props


def test_questions_schema_shape():
    assert QUESTIONS_SCHEMA["type"] == "object"
    assert "categories" in QUESTIONS_SCHEMA["properties"]


def test_evaluation_schema_score_range():
    crit_item = EVALUATION_SCHEMA["properties"]["criteria"]["items"]
    score = crit_item["properties"]["score"]
    assert score["minimum"] == 1
    assert score["maximum"] == 5


def test_evaluation_schema_criteria_count_constraint():
    criteria = EVALUATION_SCHEMA["properties"]["criteria"]
    assert criteria["minItems"] == 10
    assert criteria["maxItems"] == 10


def test_questions_schema_categories_count_constraint():
    categories = QUESTIONS_SCHEMA["properties"]["categories"]
    assert categories["minItems"] == 5
    assert categories["maxItems"] == 5


def test_questions_schema_per_category_question_constraint():
    cat_item = QUESTIONS_SCHEMA["properties"]["categories"]["items"]
    questions = cat_item["properties"]["questions"]
    assert questions["minItems"] == 3
    assert questions["maxItems"] == 5
