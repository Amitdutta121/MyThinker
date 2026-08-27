from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from mythinking.documents import Document, DocumentChunk
from mythinking.retrieval import (
    delete_document,
    delete_documents,
    index_chunk,
    index_content,
    index_document,
    list_chunks,
    list_documents,
    open_document_store,
    search_content,
)


class FakeEmbeddings(Embeddings):
    """Fixed, content-derived vectors -- no live network call."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        return [
            1.0 if "churn" in lowered else 0.0,
            1.0 if "pricing" in lowered else 0.0,
            float(len(text) % 5),
            1.0,
        ]


def _open_store(tmp_path: Path):
    return open_document_store(tmp_path / "store.sqlite", FakeEmbeddings(), dimensions=4)


def test_index_and_search_content_ranks_by_similarity(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store:
        index_content(
            store, "proj1", "evidence", "ev1", "users churn during onboarding", kind="fact"
        )
        index_content(
            store, "proj1", "evidence", "ev2", "pricing page conversion is low", kind="fact"
        )

        results = search_content(store, "proj1", "evidence", "why do users churn", top_k=1)

        assert len(results) == 1
        assert results[0].key == "ev1"
        assert results[0].value["kind"] == "fact"


def test_search_content_is_scoped_to_project(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store:
        index_content(store, "proj1", "evidence", "ev1", "users churn during onboarding")
        index_content(store, "proj2", "evidence", "ev1", "unrelated project's own churn note")

        results = search_content(store, "proj1", "evidence", "churn", top_k=5)

        assert [item.key for item in results] == ["ev1"]


def test_index_document_and_chunks_round_trip(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store:
        document = Document(
            project_id="proj1",
            title="A source",
            source_url="https://example.com",
            content="full text",
        )
        chunk_one = DocumentChunk(
            document_id=document.id, project_id="proj1", chunk_index=0, text="pricing details here"
        )
        chunk_two = DocumentChunk(
            document_id=document.id, project_id="proj1", chunk_index=1, text="more pricing content"
        )

        index_document(store, "proj1", document)
        index_chunk(store, "proj1", chunk_one)
        index_chunk(store, "proj1", chunk_two)

        documents = list_documents(store, "proj1")
        chunks = list_chunks(store, "proj1", document.id)

        assert [d.id for d in documents] == [document.id]
        assert documents[0].title == "A source"
        assert {c.id for c in chunks} == {chunk_one.id, chunk_two.id}


def test_list_chunks_filters_by_document_id(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store:
        other_document_id = "other-doc"
        chunk = DocumentChunk(
            document_id="doc1", project_id="proj1", chunk_index=0, text="pricing content"
        )
        unrelated = DocumentChunk(
            document_id=other_document_id,
            project_id="proj1",
            chunk_index=0,
            text="pricing content too",
        )
        index_chunk(store, "proj1", chunk)
        index_chunk(store, "proj1", unrelated)

        chunks = list_chunks(store, "proj1", "doc1")

        assert [c.id for c in chunks] == [chunk.id]


def test_delete_document_removes_doc_and_chunks(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store:
        keep = Document(project_id="proj1", title="Keep", content="keep text")
        drop = Document(project_id="proj1", title="Drop", content="drop text")
        for doc in (keep, drop):
            index_document(store, "proj1", doc)
        for index in range(2):
            index_chunk(
                store,
                "proj1",
                DocumentChunk(
                    document_id=drop.id,
                    project_id="proj1",
                    chunk_index=index,
                    text=f"chunk {index}",
                ),
            )

        delete_document(store, "proj1", drop.id)

        assert [d.id for d in list_documents(store, "proj1")] == [keep.id]
        assert list_chunks(store, "proj1", drop.id) == []


def test_delete_document_unknown_id_raises_keyerror(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store, pytest.raises(KeyError):
        delete_document(store, "proj1", "nope")


def test_delete_document_clears_more_chunks_than_one_page(tmp_path: Path, monkeypatch) -> None:
    import mythinking.retrieval as retrieval_module

    real_list_chunks = retrieval_module.list_chunks

    def small_page(store, project_id, document_id, *, limit=1000):
        return real_list_chunks(store, project_id, document_id, limit=2)

    with _open_store(tmp_path) as store:
        doc = Document(project_id="proj1", title="Big")
        index_document(store, "proj1", doc)
        for index in range(5):
            index_chunk(
                store,
                "proj1",
                DocumentChunk(
                    document_id=doc.id, project_id="proj1", chunk_index=index, text=f"c{index}"
                ),
            )

        monkeypatch.setattr(retrieval_module, "list_chunks", small_page)
        retrieval_module.delete_document(store, "proj1", doc.id)

        assert real_list_chunks(store, "proj1", doc.id) == []


def test_delete_documents_removes_many_and_skips_unknown(tmp_path: Path) -> None:
    with _open_store(tmp_path) as store:
        keep = Document(project_id="proj1", title="Keep")
        drop_a = Document(project_id="proj1", title="Drop A")
        drop_b = Document(project_id="proj1", title="Drop B")
        for doc in (keep, drop_a, drop_b):
            index_document(store, "proj1", doc)

        delete_documents(store, "proj1", [drop_a.id, "ghost", drop_b.id])

        assert [d.id for d in list_documents(store, "proj1")] == [keep.id]
