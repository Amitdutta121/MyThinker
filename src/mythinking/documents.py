"""Full-text research documents and chunks, kept out of the small ProjectState blob."""

from pydantic import BaseModel, Field

from mythinking.state import new_id, utc_now


class Document(BaseModel):
    """A single fetched research source, in full, outside ProjectState."""

    id: str = Field(default_factory=new_id)
    project_id: str
    research_task_id: str = ""
    source_url: str = ""
    title: str = ""
    content: str = ""
    fetched_at: str = Field(default_factory=lambda: utc_now().isoformat())


class DocumentChunk(BaseModel):
    """One chunk of a Document's content, the unit that gets embedded and retrieved."""

    id: str = Field(default_factory=new_id)
    document_id: str
    project_id: str
    chunk_index: int
    text: str
    page: int | None = None
    document_title: str = ""


def chunk_text(text: str, *, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Split text into overlapping, size-bounded chunks.

    Deterministic and dependency-free: splits on paragraph boundaries where
    possible, falling back to a hard character cut only when a single
    paragraph exceeds `max_chars`.
    """
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            for start in range(0, len(paragraph), max_chars - overlap):
                chunks.append(paragraph[start : start + max_chars])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def chunk_pages(
    pages: list[str], *, max_chars: int = 1500, overlap: int = 200
) -> list[tuple[int, str]]:
    """Chunk each page separately, tagging every chunk with its 1-based page number.

    Used for PDFs so a retrieved passage can be cited as ``[[file.pdf p.3]]``.
    """
    numbered: list[tuple[int, str]] = []
    for page_number, page_text in enumerate(pages, start=1):
        for chunk in chunk_text(page_text, max_chars=max_chars, overlap=overlap):
            numbered.append((page_number, chunk))
    return numbered
