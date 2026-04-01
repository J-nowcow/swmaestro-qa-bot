"""청크를 임베딩하여 ChromaDB에 저장 (REST API 직접 호출)"""
import json
import os
import time
from pathlib import Path

import chromadb
import requests as req

CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "swmaestro"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"


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
        resp = req.post(
            f"{EMBED_URL}?key={api_key}",
            json=payload,
            verify=False,  # SSL 프록시 환경 호환
            timeout=60,
        )
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"  Rate limit 도달, {wait}초 대기...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    data = resp.json()

    return [item["values"] for item in data["embeddings"]]


def embed_query(text: str) -> list[float]:
    """단일 질문 임베딩"""
    return embed_texts([text])[0]


def build_index(chunks_file: str = "data/processed/chunks.json"):
    """청크 파일에서 ChromaDB 인덱스를 생성"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        print("청크가 없습니다.")
        return

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    batch_size = 10
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["content"] for c in batch]
        metadatas = [c["metadata"] for c in batch]
        ids = [f"chunk_{i + j}" for j in range(len(batch))]

        vectors = embed_texts(texts)

        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"  [{i + len(batch)}/{total}] 인덱싱 완료")
        time.sleep(5)  # rate limit (15 RPM)

    print(f"\nChromaDB 인덱스 생성 완료: {CHROMA_DIR} ({total}개 청크)")


def get_collection():
    """저장된 ChromaDB 컬렉션 반환"""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_collection(COLLECTION_NAME)
