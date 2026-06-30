from pathlib import Path

from .text import normalize_text


def split_markdown(text: str, max_chars: int = 650, overlap: int = 80) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "正文"
    current_lines: list[str] = []

    for line in normalize_text(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = stripped.lstrip("#").strip() or current_title
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))

    chunks: list[tuple[str, str]] = []
    for title, lines in sections:
        section_text = normalize_text("\n".join(lines))
        chunks.extend(_split_by_length(title, section_text, max_chars, overlap))
    return chunks


def split_plain_text(text: str, max_chars: int = 650, overlap: int = 80) -> list[tuple[str, str]]:
    sections = _split_plain_sections(normalize_text(text))
    chunks: list[tuple[str, str]] = []
    for title, section_text in sections:
        chunks.extend(_split_by_length(title, section_text, max_chars, overlap))
    return chunks


def split_file(path: Path, max_chars: int = 650, overlap: int = 80) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".md", ".markdown"}:
        return split_markdown(text, max_chars=max_chars, overlap=overlap)
    return split_plain_text(text, max_chars=max_chars, overlap=overlap)


def _split_by_length(title: str, text: str, max_chars: int, overlap: int) -> list[tuple[str, str]]:
    if len(text) <= max_chars:
        return [(title, text)] if text else []

    chunks: list[tuple[str, str]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        window = text[start:end]
        split_at = max(window.rfind("\n\n"), window.rfind("。"), window.rfind("."))
        if split_at > max_chars * 0.5 and end < len(text):
            end = start + split_at + 1
        chunk = normalize_text(text[start:end])
        if chunk:
            chunks.append((title, chunk))
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _split_plain_sections(text: str) -> list[tuple[str, str]]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        return []

    sections: list[tuple[str, str]] = []
    current_title = paragraphs[0][:60]
    current_parts: list[str] = [paragraphs[0]]

    for paragraph in paragraphs[1:]:
        if _looks_like_heading(paragraph):
            if current_parts:
                sections.append((current_title, "\n\n".join(current_parts)))
            current_title = paragraph
            current_parts = [paragraph]
        else:
            current_parts.append(paragraph)

    if current_parts:
        sections.append((current_title, "\n\n".join(current_parts)))
    return sections


def _looks_like_heading(paragraph: str) -> bool:
    if "\n" in paragraph:
        return False
    if len(paragraph) > 32:
        return False
    return not paragraph.endswith(("。", ".", "；", ";", "，", ","))
