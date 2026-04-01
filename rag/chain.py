"""RAG 체인: 검색된 컨텍스트 + Gemini REST API로 답변 생성 (모델 폴백 포함)"""
import os
import time
import urllib3
from datetime import datetime, timezone, timedelta

import requests as req

from rag.retriever import retrieve

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

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
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[출처 {i}] {r['page_title']} - {r['section']}\n"
            f"URL: {r['source_url']}\n"
            f"내용: {r['content']}\n"
        )
    return "\n---\n".join(parts)


def _call_gemini(messages: list[dict]) -> str:
    """모델 폴백 포함 Gemini REST API 호출"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": messages,
        "generationConfig": {"temperature": 0.3},
    }

    last_error = None
    for model in FALLBACK_MODELS:
        url = f"{BASE_URL}/{model}:generateContent?key={api_key}"

        for attempt in range(2):
            resp = req.post(url, json=payload, verify=False, timeout=60)
            if resp.status_code == 429:
                if attempt == 0:
                    time.sleep(5)
                    continue
                break  # 다음 모델로
            if resp.status_code == 200:
                data = resp.json()
                if "candidates" in data:
                    print(f"[LLM] model={model} ok")
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            last_error = resp.text
            break

        print(f"[LLM] model={model} rate limited, trying next...")

    return "현재 요청이 많아 답변을 생성할 수 없습니다. 잠시 후 다시 시도해주세요."


def log_query(question: str, answer: str):
    """질문/답변 로그 기록"""
    kst = timezone(timedelta(hours=9))
    ts = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[LOG] {ts} | Q: {question[:80]}")

    # Google Sheets 웹훅 (설정된 경우)
    webhook_url = os.getenv("LOG_WEBHOOK_URL")
    if webhook_url:
        try:
            req.post(webhook_url, json={
                "timestamp": ts,
                "question": question,
                "answer_preview": answer[:100],
                "answer_length": len(answer),
            }, timeout=5)
        except Exception:
            pass


def ask(question: str, chat_history: list[dict] | None = None) -> str:
    results = retrieve(question, top_k=5)

    if not results:
        return "관련 정보를 찾을 수 없습니다. 공식 사이트(https://swmaestro.ai)를 확인해주세요."

    context = build_context(results)
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

    answer = _call_gemini(messages)
    log_query(question, answer)
    return answer
