from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from mythinking.ingest import MAX_UPLOAD_BYTES, IngestError, ingest_file
from mythinking.retrieval import list_chunks, list_documents, open_document_store


def _make_pdf(text: str) -> bytes:
    """Build a spec-compliant single-page PDF (exact xref offsets) that draws
    `text`, so the real pypdf extraction path can be exercised without a
    PDF-writing dependency."""

    stream = b"BT /F1 24 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(bodies) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(bodies) + 1)
    out += b"startxref\n%d\n%%%%EOF" % xref_pos
    return bytes(out)


_MINIMAL_PDF = _make_pdf("Hello World")


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


@pytest.fixture
def store(tmp_path: Path):
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as opened:
        yield opened


def test_ingest_markdown_stores_document_and_chunks(store) -> None:
    result = ingest_file(
        store, "proj-1", filename="notes.md", data=b"# Title\n\nA paragraph of body text."
    )

    assert result.document.title == "notes.md"
    assert result.document.source_url == "notes.md"  # defaults to the filename
    assert result.page_count == 0
    assert result.chunk_count >= 1

    docs = list_documents(store, "proj-1")
    assert [d.id for d in docs] == [result.document.id]
    chunks = list_chunks(store, "proj-1", result.document.id)
    assert chunks and all(c.page is None for c in chunks)


def test_ingest_pdf_extracts_text_and_pages(store) -> None:
    result = ingest_file(store, "proj-1", filename="paper.pdf", data=_MINIMAL_PDF)

    assert result.page_count == 1
    assert result.chunk_count >= 1
    assert "Hello World" in result.document.content
    chunks = list_chunks(store, "proj-1", result.document.id)
    assert all(c.page == 1 for c in chunks)


def test_ingest_rejects_unsupported_type(store) -> None:
    with pytest.raises(IngestError, match="Unsupported file type"):
        ingest_file(store, "proj-1", filename="archive.zip", data=b"PK\x03\x04")


def test_ingest_rejects_empty_file(store) -> None:
    with pytest.raises(IngestError, match="empty"):
        ingest_file(store, "proj-1", filename="notes.txt", data=b"")


def test_ingest_rejects_oversized_file(store) -> None:
    with pytest.raises(IngestError, match="larger than"):
        ingest_file(store, "proj-1", filename="big.txt", data=b"x" * (MAX_UPLOAD_BYTES + 1))


def test_ingest_rejects_non_utf8_text(store) -> None:
    with pytest.raises(IngestError, match="UTF-8"):
        ingest_file(store, "proj-1", filename="notes.txt", data=b"\xff\xfe\x00bad")


def test_ingest_rejects_unreadable_pdf(store) -> None:
    with pytest.raises(IngestError, match="Could not read the PDF"):
        ingest_file(store, "proj-1", filename="broken.pdf", data=b"not really a pdf")


def test_ingest_rejects_text_with_no_content(store) -> None:
    with pytest.raises(IngestError, match="no extractable text"):
        ingest_file(store, "proj-1", filename="blank.txt", data=b"   \n\t  ")
