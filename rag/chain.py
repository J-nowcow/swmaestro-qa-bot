"""RAG 체인: 검색된 컨텍스트 + Gemini REST API로 답변 생성"""
import os
import urllib3

import requests as req

from rag.retriever import retrieve

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CHAT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_PROMPT = """당신은 AI·SW마에스트로 프로그램의 공식 정보를 기반으로 답변하는 Q&A 어시스턴트입니다.

## 규칙
1. 아래 제공된 컨텍스트 정보만을 기반으로 답변하세요.
2. 컨텍스트에 없는 내용은 "해당 정보는 공식 자료에서 확인되지 않습니다. 공식 사이트(swmaestro.ai)를 참고해주세요."라고 답변하세요.
3. 답변은 명확하고 친절하게 작성하세요.
4. **답변 끝에 반드시 출처를 표시하세요.** 형식:

📎 출처:
- [페이지 제목 - 섹션](URL)

5. 출처는 실제로 답변에 사용한 컨텍스트의 URL만 포함하세요.
"""


def build_context(results: list[dict]) -> str:
    """검색 결과를 컨텍스트 문자열로 변환"""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[출처 {i}] {r['page_title']} - {r['section']}\n"
            f"URL: {r['source_url']}\n"
            f"내용: {r['content']}\n"
        )
    return "\n---\n".join(parts)


def _call_gemini(messages: list[dict]) -> str:
    """Gemini REST API 직접 호출"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": messages,
        "generationConfig": {"temperature": 0.3},
    }

    import time
    for attempt in range(3):
        resp = req.post(
            f"{CHAT_URL}?key={api_key}",
            json=payload,
            verify=False,
            timeout=60,
        )
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    data = resp.json()

    if "error" in data:
        return f"API 오류가 발생했습니다: {data['error'].get('message', '알 수 없는 오류')}. 잠시 후 다시 시도해주세요."

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return "답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."


def ask(question: str, chat_history: list[dict] | None = None) -> str:
    """질문에 대한 답변 생성

    Args:
        question: 사용자 질문
        chat_history: 이전 대화 기록 [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        답변 문자열 (출처 포함)
    """
    # 1) 관련 문서 검색
    results = retrieve(question, top_k=5)

    if not results:
        return "관련 정보를 찾을 수 없습니다. 공식 사이트(https://swmaestro.ai)를 확인해주세요."

    # 2) 컨텍스트 구성
    context = build_context(results)

    # 3) 메시지 구성 (Gemini API 형식)
    messages = []

    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg["role"] == "user" else "model"
            messages.append({"role": role, "parts": [{"text": msg["content"]}]})

    user_message = f"""## 참고 컨텍스트
{context}

## 질문
{question}"""

    messages.append({"role": "user", "parts": [{"text": user_message}]})

    # 4) LLM 호출
    return _call_gemini(messages)
