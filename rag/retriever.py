"""ChromaDB에서 유사 청크를 검색"""
from rag.embedder import get_collection, embed_query


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """질문과 가장 유사한 청크를 검색하여 반환

    Returns:
        list of dict: 각 항목은 content, source_url, page_title, section 포함
    """
    collection = get_collection()
    query_vector = embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        retrieved.append({
            "content": doc,
            "source_url": meta.get("source_url", ""),
            "page_title": meta.get("page_title", ""),
            "section": meta.get("section", ""),
            "distance": dist,
        })

    return retrieved
