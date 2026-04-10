"""Compose evaluation + question results into a single markdown page."""
from __future__ import annotations


def _stars(score: int) -> str:
    score = max(0, min(5, int(score)))
    return "⭐" * score + "☆" * (5 - score)


def compose_result_md(
    evaluation: dict,
    questions: dict | None,
    metadata: dict,
) -> str:
    """Render evaluation (and optional questions) as a single markdown page.

    Args:
        evaluation: dict with keys 'overall' and 'criteria' (10 items).
        questions: dict with key 'categories' (5 items), or None on Call 2 failure.
        metadata: dict with 'timestamp', 'model_used', 'page_count', 'image_count', 'image_truncated'.
    """
    out: list[str] = []

    out.append("# 포트폴리오 평가 결과")
    out.append("")
    out.append(f"> 분석 일시: {metadata.get('timestamp', '')}")
    out.append(f"> 사용 모델: {metadata.get('model_used', '')}")
    out.append("")

    overall = evaluation.get("overall", {})
    out.append("## 📊 종합 평가")
    out.append("")
    out.append(f"**한 줄 총평**: {overall.get('one_liner', '')}")
    out.append("")
    out.append("**강점**")
    for s in overall.get("strengths", []):
        out.append(f"- {s}")
    out.append("")
    out.append("**약점**")
    for w in overall.get("weaknesses", []):
        out.append(f"- {w}")
    out.append("")

    out.append("## 📝 10항목 상세 평가")
    out.append("")
    for c in evaluation.get("criteria", []):
        out.append(f"### {c.get('id')}. {c.get('title', '')}")
        out.append(_stars(c.get("score", 0)) + f" ({c.get('score', 0)}/5)")
        out.append("")
        out.append(f"**평가**: {c.get('evaluation', '')}")
        out.append("")
        out.append(f"**근거**: {c.get('evidence', '')}")
        out.append("")

    if questions is not None and questions.get("categories"):
        out.append("## 🎤 예상 면접 질문")
        out.append("")
        for i, cat in enumerate(questions["categories"], start=1):
            out.append(f"### {i}. {cat.get('name', '')}")
            for q in cat.get("questions", []):
                out.append(f"- Q: {q}")
            rationale = cat.get("rationale", "")
            if rationale:
                out.append("")
                out.append(f"_왜 이 질문이 나올까: {rationale}_")
            out.append("")
    else:
        out.append("## ⚠️ 면접 질문 생성에 실패했습니다")
        out.append("평가는 정상 생성되었습니다. 잠시 후 새로 분석을 시도해주세요.")
        out.append("")

    out.append("## 📌 분석 노트")
    _pc = metadata.get("page_count")
    page_count = "?" if _pc is None else _pc
    _ic = metadata.get("image_count")
    image_count = "?" if _ic is None else _ic
    truncated = metadata.get("image_truncated", False)
    image_note = f"{image_count} (첫 30장만 분석)" if truncated else f"{image_count} (전부 분석 포함)"
    out.append(f"- 페이지 수: {page_count}")
    out.append(f"- 이미지 수: {image_note}")
    out.append(f"- 모델: {metadata.get('model_used', '')}")
    out.append("")

    out.append("---")
    out.append("")
    out.append(
        "_📚 이 도구의 10가지 평가 기준은 카카오톡 오픈채팅방 "
        "**'소프트웨어 마에스트로 준비방'** 에서 "
        "**엄지척 재이지(SW마에스트로 15기)** 님이 공유해주신 "
        "포트폴리오 꿀팁을 기반으로 만들어졌습니다._"
    )
    out.append("")

    return "\n".join(out)
