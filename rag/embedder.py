"""임베딩 및 벡터 검색 (numpy 기반, 외부 DB 불필요)"""
import json
import os
import time
from pathlib import Path

import numpy as np
import requests as req

VECTOR_STORE_PATH = "data/vector_store.json"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"

_store_cache = None


def _get_api_key():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Gemini REST API로 텍스트 임베딩 생성"""
    api_key = _get_api_key()
    payload = {
        "requests": [
            {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": t}]}}
            for t in texts
        ]
    }
    for attempt in range(3):
        resp = req.post(f"{EMBED_URL}?key={api_key}", json=payload, verify=False, timeout=60)
        if resp.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        resp.raise_for_status()
        break
    return [item["values"] for item in resp.json()["embeddings"]]


def embed_query(text: str) -> list[float]:
    """단일 질문 임베딩"""
    return embed_texts([text])[0]


def load_store() -> dict:
    """벡터 스토어 로드 (캐시)"""
    global _store_cache
    if _store_cache is None:
        with open(VECTOR_STORE_PATH, "r", encoding="utf-8") as f:
            _store_cache = json.load(f)
        _store_cache["_embeddings_np"] = np.array(_store_cache["embeddings"])
    return _store_cache


def search(query_vector: list[float], top_k: int = 5) -> list[dict]:
    """코사인 유사도로 검색"""
    store = load_store()
    emb_matrix = store["_embeddings_np"]

    q = np.array(query_vector)
    # 코사인 유사도
    q_norm = q / (np.linalg.norm(q) + 1e-10)
    emb_norms = emb_matrix / (np.linalg.norm(emb_matrix, axis=1, keepdims=True) + 1e-10)
    similarities = emb_norms @ q_norm

    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        results.append({
            "content": store["documents"][idx],
            "source_url": store["metadatas"][idx].get("source_url", ""),
            "page_title": store["metadatas"][idx].get("page_title", ""),
            "section": store["metadatas"][idx].get("section", ""),
            "similarity": float(similarities[idx]),
        })
    return results
