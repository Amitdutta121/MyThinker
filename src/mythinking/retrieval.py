"""Storage and semantic retrieval for research documents and growing project state.

Backed by `langgraph.store.sqlite.SqliteStore` -- an already-installed, official
LangGraph component (via the `langgraph-checkpoint-sqlite` dependency) that
provides namespace-scoped key/value storage with optional sqlite-vec-backed
vector search. This module is a thin, typed wrapper around it, not a new
storage engine: no custom schema or SQL is introduced here.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from langgraph.store.base import SearchItem
from langgraph.store.sqlite import SqliteStore

from mythinking.documents import Document, DocumentChunk


@contextmanager
def open_document_store(
    database_path: Path,
    embeddings: Embeddings,
    *,
    dimensions: int,
) -> Iterator[SqliteStore]:
    """Open the shared store used for document/chunk storage and semantic retrieval.

    A separate SQLite file from `state.sqlite`/`checkpoints.sqlite`: `SqliteStore`
    wants one long-lived, autocommit connection (its own internal lock), which
    is a different lifecycle from `StateRepository`'s per-call WAL connections
    -- the same reason `checkpoints.sqlite` is already its own file.
    """

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteStore.from_conn_string(
        str(database_path),
        index={"dims": dimensions, "embed": embeddings, "fields": ["text"]},
    ) as store:
        store.setup()
        yield store


def index_document(store: SqliteStore, project_id: str, document: Document) -> None:
    """Store a document's metadata/content without embedding it -- chunks are what get indexed."""

    store.put((project_id, "document"), document.id, document.model_dump(mode="json"), index=False)


def index_chunk(store: SqliteStore, project_id: str, chunk: DocumentChunk) -> None:
    store.put(
        (project_id, "document_chunk"),
        chunk.id,
        {"text": chunk.text, **chunk.model_dump(mode="json")},
    )


def index_content(
    store: SqliteStore,
    project_id: str,
    content_type: str,
    content_id: str,
    text: str,
    **metadata: Any,
) -> None:
    """Index one item of growing project state (evidence, research task, decision) for retrieval."""

    store.put((project_id, content_type), content_id, {"text": text, **metadata})


def search_content(
    store: SqliteStore,
    project_id: str,
    content_type: str,
    query: str,
    *,
    top_k: int,
) -> list[SearchItem]:
    return store.search((project_id, content_type), query=query, limit=top_k)


def list_documents(store: SqliteStore, project_id: str, *, limit: int = 1000) -> list[Document]:
    items = store.search((project_id, "document"), limit=limit)
    return [Document.model_validate(item.value) for item in items]


def list_chunks(
    store: SqliteStore,
    project_id: str,
    document_id: str,
    *,
    limit: int = 1000,
) -> list[DocumentChunk]:
    items = store.search(
        (project_id, "document_chunk"),
        filter={"document_id": document_id},
        limit=limit,
    )
    return [DocumentChunk.model_validate(item.value) for item in items]


def delete_document(store: SqliteStore, project_id: str, document_id: str) -> None:
    """Remove a document and all its indexed chunks. Raises KeyError if unknown."""

    if store.get((project_id, "document"), document_id) is None:
        raise KeyError(f"Unknown document_id: {document_id}")
    # `list_chunks` returns a single capped page; loop so a large document (a PDF
    # that produced more than `limit` chunks) is cleared completely rather than
    # leaving orphan chunks that still answer `search_documents`.
    while chunks := list_chunks(store, project_id, document_id):
        for chunk in chunks:
            store.delete((project_id, "document_chunk"), chunk.id)
    store.delete((project_id, "document"), document_id)


def delete_documents(
    store: SqliteStore, project_id: str, document_ids: Iterable[str]
) -> None:
    """Remove several documents and their chunks. Unknown ids are skipped."""

    for document_id in document_ids:
        try:
            delete_document(store, project_id, document_id)
        except KeyError:
            continue
