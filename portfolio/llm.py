"""Gemini REST API call with multimodal support and 8-model fallback.

Pattern adapted from rag/chain.py:_call_gemini, extended for inline_data parts.
"""
from __future__ import annotations

import os
import urllib3
from typing import Callable

import requests as req

from portfolio.parser import ImageData

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Multimodal-capable models, ordered by preference
MM_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]

# Text-only fallbacks (used after MM models exhausted; images are dropped)
TEXT_FALLBACK = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
]


class LLMUnavailableError(Exception):
    """Raised when all models in the fallback chain fail."""


def _build_parts(user_text: str, images: list[ImageData] | None) -> list[dict]:
    parts: list[dict] = [{"text": user_text}]
    if images:
        for img in images:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": img.mime_type,
                        "data": img.base64,
                    }
                }
            )
    return parts


def _build_payload(
    system_prompt: str,
    parts: list[dict],
    response_schema: dict | None,
) -> dict:
    payload: dict = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.3},
    }
    if response_schema is not None:
        payload["generationConfig"]["responseMimeType"] = "application/json"
        payload["generationConfig"]["responseSchema"] = response_schema
    return payload


def _try_model(
    model: str,
    payload: dict,
    api_key: str,
) -> tuple[str, dict] | None:
    """Returns (text, tokens) on 200, None on 429/error."""
    url = f"{BASE_URL}/{model}:generateContent?key={api_key}"
    try:
        resp = req.post(url, json=payload, verify=False, timeout=120)
    except Exception as e:
        print(f"[PORTFOLIO LLM] {model} request error: {e}", flush=True)
        return None
    if resp.status_code == 200:
        data = resp.json()
        if "candidates" in data:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            tokens = {
                "input": usage.get("promptTokenCount", 0),
                "output": usage.get("candidatesTokenCount", 0),
            }
            print(f"[PORTFOLIO LLM] model={model} ok", flush=True)
            return text, tokens
        return None
    if resp.status_code == 429:
        print(f"[PORTFOLIO LLM] model={model} rate limited", flush=True)
        return None
    print(f"[PORTFOLIO LLM] model={model} status={resp.status_code}", flush=True)
    return None


def call_multimodal(
    system_prompt: str,
    user_text: str,
    images: list[ImageData] | None = None,
    response_schema: dict | None = None,
    api_key: str | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> tuple[str, str, dict]:
    """Call Gemini with multimodal payload, with 8-model fallback.

    Returns:
        (response_text, model_used, token_usage_dict)

    Raises:
        ValueError: if API key is missing.
        LLMUnavailableError: if all models in the chain fail.
    """
    key = (
        api_key
        or os.getenv("GOOGLE_API_KEY_PORTFOLIO")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not key:
        raise ValueError("GOOGLE_API_KEY is not set and no api_key was provided")

    parts_with_images = _build_parts(user_text, images)
    payload_with_images = _build_payload(system_prompt, parts_with_images, response_schema)

    # Pass 1: multimodal-capable models with images
    for i, model in enumerate(MM_MODELS):
        result = _try_model(model, payload_with_images, key)
        if result is not None:
            text, tokens = result
            return text, model, tokens
        if status_callback and i + 1 < len(MM_MODELS):
            status_callback(f"요청이 많아 대체 모델({MM_MODELS[i + 1]})로 시도 중...")

    # Pass 2: text-only fallback (drop images)
    parts_text_only = _build_parts(user_text, None)
    payload_text_only = _build_payload(system_prompt, parts_text_only, response_schema)
    for i, model in enumerate(TEXT_FALLBACK):
        result = _try_model(model, payload_text_only, key)
        if result is not None:
            text, tokens = result
            if status_callback:
                status_callback(f"이미지 분석을 건너뛴 텍스트 모드로 답변했습니다 ({model}).")
            return text, model, tokens

    raise LLMUnavailableError("All Gemini models in the fallback chain failed")
