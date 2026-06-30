from .models import SearchResult


def generate_answer(question: str, results: list[SearchResult], min_score: float = 0.08) -> str:
    if not results or results[0].final_score < min_score:
        return (
            "证据不足，当前知识库没有检索到足够相关的材料，建议补充对应文档后再查询。"
        )

    evidence_lines = []
    citation_lines = []
    for rank, result in enumerate(results[:3], start=1):
        chunk = result.chunk
        summary = _first_sentence(chunk.content)
        evidence_lines.append(f"{rank}. {summary}")
        citation_lines.append(
            f"[{rank}] {chunk.document_title} / {chunk.section_path} "
            f"(chunk={chunk.id}, score={result.final_score:.3f})"
        )

    answer = [
        f"问题：{question}",
        "",
        "回答：",
        "根据知识库中召回的材料，可以先按下面思路处理：",
        *evidence_lines,
        "",
        "引用：",
        *citation_lines,
    ]
    return "\n".join(answer)


def _first_sentence(text: str, max_chars: int = 180) -> str:
    stripped = " ".join(text.split())
    for separator in ("。", ".", "\n"):
        index = stripped.find(separator)
        if 0 < index < max_chars:
            return stripped[: index + 1]
    return stripped[:max_chars]

