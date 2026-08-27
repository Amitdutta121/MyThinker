from pathlib import Path

from langchain_core.embeddings import Embeddings

from mythinking.documents import Document, DocumentChunk
from mythinking.retrieval import (
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
