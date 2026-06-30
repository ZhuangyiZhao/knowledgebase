from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Document:
    id: str
    title: str
    path: str
    doc_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    id: str
    document_id: str
    document_title: str
    section_path: str
    content: str
    tokens: list[str]
    embedding: list[float]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    chunk: Chunk
    vector_score: float
    keyword_score: float
    final_score: float

