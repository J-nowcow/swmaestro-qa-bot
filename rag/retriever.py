"""벡터 검색으로 유사 청크를 검색"""
from rag.embedder import embed_query, search


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """질문과 가장 유사한 청크를 검색하여 반환"""
    query_vector = embed_query(query)
    return search(query_vector, top_k=top_k)
