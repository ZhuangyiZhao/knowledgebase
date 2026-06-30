import json
from pathlib import Path
from typing import Any

from .models import Chunk, Document


def load_index(index_path: Path) -> tuple[list[Document], list[Chunk]]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    documents = [Document(**item) for item in payload.get("documents", [])]
    chunks = [Chunk(**item) for item in payload.get("chunks", [])]
    return documents, chunks


def save_index(index_path: Path, documents: list[Document], chunks: list[Chunk]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "documents": [document.to_dict() for document in documents],
        "chunks": [chunk.to_dict() for chunk in chunks],
    }
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

