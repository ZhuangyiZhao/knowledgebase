import math
from collections import Counter

from .embedding import cosine_similarity, embed_text
from .models import Chunk, SearchResult
from .text import tokenize


def search_chunks(chunks: list[Chunk], question: str, top_k: int = 5) -> list[SearchResult]:
    query_tokens = tokenize(question)
    query_embedding = embed_text(question)
    document_frequency = _document_frequency(chunks)
    total_chunks = len(chunks)

    scored: list[SearchResult] = []
    for chunk in chunks:
        vector_score = max(0.0, cosine_similarity(query_embedding, chunk.embedding))
        keyword_score = _tf_idf_score(query_tokens, chunk.tokens, document_frequency, total_chunks)
        final_score = 0.6 * vector_score + 0.4 * keyword_score
        if final_score > 0:
            scored.append(SearchResult(chunk, vector_score, keyword_score, final_score))

    return sorted(scored, key=lambda item: item.final_score, reverse=True)[:top_k]


def _document_frequency(chunks: list[Chunk]) -> Counter[str]:
    frequency: Counter[str] = Counter()
    for chunk in chunks:
        frequency.update(set(chunk.tokens))
    return frequency


def _tf_idf_score(
    query_tokens: list[str],
    chunk_tokens: list[str],
    document_frequency: Counter[str],
    total_chunks: int,
) -> float:
    if not query_tokens or not chunk_tokens:
        return 0.0

    chunk_counter = Counter(chunk_tokens)
    score = 0.0
    for token in query_tokens:
        if token not in chunk_counter:
            continue
        tf = chunk_counter[token] / len(chunk_tokens)
        idf = math.log((total_chunks + 1) / (document_frequency[token] + 1)) + 1
        score += tf * idf
    return min(1.0, score * 8)

