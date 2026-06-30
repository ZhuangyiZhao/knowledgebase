import hashlib
from pathlib import Path

from .chunker import split_file
from .embedding import embed_text
from .models import Chunk, Document
from .store import save_index
from .text import title_from_markdown, tokenize


SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}


def build_index(docs_dir: Path, index_path: Path) -> tuple[int, int]:
    documents: list[Document] = []
    chunks: list[Chunk] = []

    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        raw_text = path.read_text(encoding="utf-8")
        document_id = _stable_id(str(path.relative_to(docs_dir)))
        title = title_from_markdown(raw_text, fallback=path.stem)
        document = Document(
            id=document_id,
            title=title,
            path=str(path.relative_to(docs_dir)),
            doc_type=path.suffix.lower().lstrip("."),
        )
        documents.append(document)

        for index, (section_path, content) in enumerate(split_file(path), start=1):
            chunk_id = f"{document_id}:{index:04d}"
            chunk_text = f"{title}\n{section_path}\n{content}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    document_title=title,
                    section_path=section_path,
                    content=content,
                    tokens=tokenize(chunk_text),
                    embedding=embed_text(chunk_text),
                    metadata={
                        "source_path": document.path,
                        "doc_type": document.doc_type,
                        "chunk_no": index,
                    },
                )
            )

    save_index(index_path, documents, chunks)
    return len(documents), len(chunks)


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]

