from mythinking.documents import Document, DocumentChunk, chunk_pages, chunk_text


def test_chunk_text_returns_single_chunk_when_short() -> None:
    assert chunk_text("short text") == ["short text"]


def test_chunk_text_returns_empty_list_for_blank_input() -> None:
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_splits_on_paragraph_boundaries() -> None:
    paragraphs = ["a" * 100, "b" * 100, "c" * 100]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text, max_chars=150, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 150 for chunk in chunks)
    assert "".join(paragraphs) in "".join(chunks).replace("\n\n", "")


def test_chunk_text_hard_splits_a_single_oversized_paragraph() -> None:
    text = "x" * 500

    chunks = chunk_text(text, max_chars=200, overlap=50)

    assert all(len(chunk) <= 200 for chunk in chunks)
    assert len(chunks) > 1


def test_document_and_chunk_defaults() -> None:
    document = Document(project_id="proj1", title="A source", content="body")
    chunk = DocumentChunk(document_id=document.id, project_id="proj1", chunk_index=0, text="body")

    assert document.id
    assert document.fetched_at
    assert chunk.document_id == document.id
    assert chunk.page is None
    assert chunk.document_title == ""


def test_chunk_pages_keeps_page_numbers_with_each_chunk() -> None:
    pages = ["one " + "a" * 300, "two " + "b" * 300, ""]

    numbered = chunk_pages(pages, max_chars=150, overlap=20)

    page_numbers = {page for page, _ in numbered}
    assert page_numbers == {1, 2}  # the blank third page contributes nothing
    assert all(text.strip() for _, text in numbered)
    first_page_chunks = [text for page, text in numbered if page == 1]
    assert first_page_chunks and first_page_chunks[0].startswith("one ")
