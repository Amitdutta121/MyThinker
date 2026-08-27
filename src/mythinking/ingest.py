"""One implementation of "file bytes -> stored Document + indexed chunks".

Two callers share it and neither reimplements extraction or chunking:

* the ``ingest_pdf`` agent tool -- reads a local path, hands us the bytes;
* ``POST /projects/{id}/documents`` -- hands us the uploaded request body.

Anything the caller should show the user as a rejection (rather than a 500) is
raised as :class:`IngestError`.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

from langgraph.store.sqlite import SqliteStore
from pypdf import PdfReader

from mythinking.documents import Document, DocumentChunk, chunk_pages, chunk_text
from mythinking.retrieval import index_chunk, index_document

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_TEXT_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".text"})
SUPPORTED_SUFFIXES = frozenset({".pdf", *_TEXT_SUFFIXES})


class IngestError(ValueError):
    """A rejected upload: unsupported type, empty, oversized, or no extractable text."""


@dataclass(frozen=True)
class IngestResult:
    document: Document
    page_count: int
    chunk_count: int


def ingest_file(
    store: SqliteStore,
    project_id: str,
    *,
    filename: str,
    data: bytes,
    source_url: str = "",
) -> IngestResult:
    """Extract text from ``data``, store it as a ``Document``, and index its chunks.

    ``source_url`` defaults to the filename so a locally uploaded file still has a
    stable provenance string in the ledger.
    """

    name = (filename or "").strip() or "upload"
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestError(
            f"Unsupported file type: {suffix or name!r}. Accepted: PDF, plain text, Markdown."
        )
    if not data:
        raise IngestError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise IngestError(f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")

    if suffix == ".pdf":
        pages = _pdf_pages(data)
        page_count = len(pages)
        numbered_chunks: list[tuple[int | None, str]] = list(chunk_pages(pages))
        full_text = "\n\n".join(pages)
    else:
        full_text = _decode_text(data)
        page_count = 0
        numbered_chunks = [(None, chunk) for chunk in chunk_text(full_text)]

    if not full_text.strip():
        raise IngestError(f"{name} produced no extractable text.")

    document = Document(
        project_id=project_id,
        title=name,
        source_url=source_url or name,
        content=full_text,
    )
    index_document(store, project_id, document)
    for chunk_index, (page_number, chunk) in enumerate(numbered_chunks):
        index_chunk(
            store,
            project_id,
            DocumentChunk(
                document_id=document.id,
                project_id=project_id,
                chunk_index=chunk_index,
                page=page_number,
                document_title=document.title,
                text=chunk,
            ),
        )
    return IngestResult(document=document, page_count=page_count, chunk_count=len(numbered_chunks))


def _pdf_pages(data: bytes) -> list[str]:
    # A malformed upload must surface as a rejection, never a server error, so the
    # broad catch is deliberate here (pypdf raises a range of types on garbage).
    try:
        reader = PdfReader(BytesIO(data))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise IngestError(f"Could not read the PDF: {exc}") from exc


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestError("The file is not valid UTF-8 text.") from exc
