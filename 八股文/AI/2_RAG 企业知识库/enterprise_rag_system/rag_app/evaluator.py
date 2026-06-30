import json
from pathlib import Path

from .models import Chunk
from .retriever import search_chunks


def evaluate_recall_at_k(chunks: list[Chunk], eval_path: Path, k: int = 5) -> dict[str, float]:
    cases = _load_cases(eval_path)
    if not cases:
        return {"cases": 0, f"recall@{k}": 0.0}

    hit_count = 0
    for case in cases:
        results = search_chunks(chunks, case["question"], top_k=k)
        result_ids = {result.chunk.id for result in results}
        expected_ids = set(case.get("expected_chunk_ids", []))
        if result_ids & expected_ids:
            hit_count += 1

    return {"cases": len(cases), f"recall@{k}": hit_count / len(cases)}


def _load_cases(eval_path: Path) -> list[dict]:
    cases = []
    for line in eval_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases

