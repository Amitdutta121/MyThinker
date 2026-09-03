"""HTTP API over `ThinkingRuntime` (M7a: non-streaming turns and state reads;
M7b: SSE streaming of turns).

This module is a thin adapter: every request maps directly onto an existing
`ThinkingRuntime`/`StateRepository` method. It holds no business logic of its
own, so the agent and its tools stay testable without the API running. The
direct-edit endpoints (goal, decisions, plan steps) follow the same rule -- the
deterministic mutation logic lives in `runtime.py` / `board.py`; the routes only
translate HTTP <-> method calls and map `KeyError` -> 404, `ValueError` -> 400.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mythinking.documents import Document
from mythinking.ingest import MAX_UPLOAD_BYTES, IngestError, ingest_file
from mythinking.observability import configure_tracing
from mythinking.retrieval import delete_document, delete_documents, list_documents
from mythinking.runtime import ThinkingRuntime, create_runtime
from mythinking.state import (
    AssistantTurn,
    ChatMessage,
    ProjectState,
    ThinkingMode,
    TurnStreamEvent,
    TurnStreamEventType,
)


@contextmanager
def _http_errors() -> Iterator[None]:
    """Map the runtime's `KeyError` / `ValueError` onto HTTP 404 / 400."""
    try:
        yield
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class TurnRequest(BaseModel):
    message: str = Field(min_length=1)
    project_id: str | None = None


class NorthStarPatch(BaseModel):
    title: str | None = None


class DecisionCreate(BaseModel):
    question: str = ""
    choice: str = Field(min_length=1)
    rationale: str = ""
    reversible: bool = True


class DecisionPatch(BaseModel):
    question: str | None = None
    choice: str | None = Field(default=None, min_length=1)
    rationale: str | None = None
    reversible: bool | None = None


class NextActionCreate(BaseModel):
    description: str = Field(min_length=1)
    time_box_minutes: int = Field(default=30, ge=1)
    implementation_intention: str = ""
    success_signal: str = ""
    failure_signal: str = ""


class NextActionPatch(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    time_box_minutes: int | None = Field(default=None, ge=1)
    implementation_intention: str | None = None
    success_signal: str | None = None
    failure_signal: str | None = None
    completed: bool | None = None


class DocumentDeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1)


class ProjectSummary(BaseModel):
    project_id: str
    updated_at: datetime
    current_mode: ThinkingMode
    title: str

    @classmethod
    def from_state(cls, state: ProjectState) -> "ProjectSummary":
        return cls(
            project_id=state.project_id,
            updated_at=state.updated_at,
            current_mode=state.current_mode,
            title=state.north_star.title,
        )


def create_app(runtime: ThinkingRuntime | None = None) -> FastAPI:
    """Build the API app. `runtime` defaults to a lazily constructed real one.

    Lazy construction matters because building a real `ThinkingRuntime`
    requires a configured OpenRouter API key; importing this module (or
    listing/reading project state) should not require one.
    """

    configure_tracing()
    app = FastAPI(title="MyThinking API")
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_runtime() -> ThinkingRuntime:
        if app.state.runtime is None:
            app.state.runtime = create_runtime()
        return app.state.runtime

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/turns", response_model=AssistantTurn)
    def create_turn(
        request: TurnRequest,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> AssistantTurn:
        try:
            return runtime.run_turn(request.message, project_id=request.project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/turns/stream")
    def create_turn_stream(
        request: TurnRequest,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> StreamingResponse:
        try:
            events = runtime.stream_turn(request.message, project_id=request.project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return StreamingResponse(_encode_server_sent_events(events), media_type="text/event-stream")

    @app.get("/projects", response_model=list[ProjectSummary])
    def list_projects(
        limit: int = 20,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> list[ProjectSummary]:
        return [ProjectSummary.from_state(state) for state in runtime.repository.list_recent(limit)]

    @app.get("/projects/{project_id}", response_model=ProjectState)
    def get_project(
        project_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        state = runtime.get_project_state(project_id)
        if state is None:
            raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
        return state

    @app.patch("/projects/{project_id}/north-star", response_model=ProjectState)
    def patch_north_star(
        project_id: str,
        body: NorthStarPatch,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.edit_north_star(project_id, title=body.title)

    @app.post("/projects/{project_id}/decisions", response_model=ProjectState, status_code=201)
    def create_decision(
        project_id: str,
        body: DecisionCreate,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.add_decision(
                project_id,
                question=body.question,
                choice=body.choice,
                rationale=body.rationale,
                reversible=body.reversible,
            )

    @app.patch("/projects/{project_id}/decisions/{decision_id}", response_model=ProjectState)
    def patch_decision(
        project_id: str,
        decision_id: str,
        body: DecisionPatch,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.edit_decision(
                project_id,
                decision_id,
                question=body.question,
                choice=body.choice,
                rationale=body.rationale,
                reversible=body.reversible,
            )

    @app.delete("/projects/{project_id}/decisions/{decision_id}", response_model=ProjectState)
    def delete_decision(
        project_id: str,
        decision_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.delete_decision(project_id, decision_id)

    @app.post("/projects/{project_id}/proposal/approve", response_model=ProjectState)
    def approve_proposal(
        project_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.approve_proposal(project_id)

    @app.delete("/projects/{project_id}/proposal", response_model=ProjectState)
    def dismiss_proposal(
        project_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.dismiss_proposal(project_id)

    @app.post("/projects/{project_id}/next-actions", response_model=ProjectState, status_code=201)
    def create_next_action(
        project_id: str,
        body: NextActionCreate,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.add_next_action(
                project_id,
                description=body.description,
                time_box_minutes=body.time_box_minutes,
                implementation_intention=body.implementation_intention,
                success_signal=body.success_signal,
                failure_signal=body.failure_signal,
            )

    @app.patch("/projects/{project_id}/next-actions/{action_id}", response_model=ProjectState)
    def patch_next_action(
        project_id: str,
        action_id: str,
        body: NextActionPatch,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.edit_next_action(
                project_id,
                action_id,
                description=body.description,
                time_box_minutes=body.time_box_minutes,
                implementation_intention=body.implementation_intention,
                success_signal=body.success_signal,
                failure_signal=body.failure_signal,
                completed=body.completed,
            )

    @app.delete("/projects/{project_id}/next-actions/{action_id}", response_model=ProjectState)
    def delete_next_action(
        project_id: str,
        action_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> ProjectState:
        with _http_errors():
            return runtime.delete_next_action(project_id, action_id)

    @app.get("/projects/{project_id}/messages", response_model=list[ChatMessage])
    def get_project_messages(
        project_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> list[ChatMessage]:
        try:
            return runtime.get_history(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/projects/{project_id}/documents", response_model=list[Document])
    def list_project_documents(
        project_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> list[Document]:
        if runtime.store is None:
            return []
        return list_documents(runtime.store, project_id)

    @app.post(
        "/projects/{project_id}/documents",
        response_model=Document,
        status_code=201,
    )
    async def upload_project_document(
        project_id: str,
        filename: str,
        request: Request,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> Document:
        """Ingest an uploaded file (PDF / text / Markdown) into the project's
        document store so it can be cited in later turns.

        The raw file bytes are the request body; `filename` (a query parameter)
        drives type detection and provenance. Kept as a raw-body upload rather
        than multipart so no extra parser dependency is needed.
        """
        if runtime.get_project_state(project_id) is None:
            raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
        if runtime.store is None:
            raise HTTPException(
                status_code=503, detail="Document storage is not configured on this server."
            )

        declared_length = request.headers.get("content-length")
        if (
            declared_length is not None
            and declared_length.isdigit()
            and int(declared_length) > MAX_UPLOAD_BYTES
        ):
            raise HTTPException(
                status_code=413,
                detail=f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )

        data = await request.body()
        try:
            result = ingest_file(runtime.store, project_id, filename=filename, data=data)
        except IngestError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.document

    @app.delete(
        "/projects/{project_id}/documents/{document_id}",
        response_model=list[Document],
    )
    def delete_project_document(
        project_id: str,
        document_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> list[Document]:
        """Remove one stored source (and its indexed chunks) from the project."""
        if runtime.store is None:
            raise HTTPException(
                status_code=503, detail="Document storage is not configured on this server."
            )
        try:
            delete_document(runtime.store, project_id, document_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return list_documents(runtime.store, project_id)

    @app.post(
        "/projects/{project_id}/documents/delete",
        response_model=list[Document],
    )
    def delete_project_documents(
        project_id: str,
        body: DocumentDeleteRequest,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> list[Document]:
        """Remove several stored sources at once. Unknown ids are ignored."""
        if runtime.store is None:
            raise HTTPException(
                status_code=503, detail="Document storage is not configured on this server."
            )
        delete_documents(runtime.store, project_id, body.ids)
        return list_documents(runtime.store, project_id)

    return app


def _encode_server_sent_events(events: Iterator[TurnStreamEvent]) -> Iterator[str]:
    """Render each event as one `text/event-stream` frame.

    Broad `except Exception` is deliberate here, not elsewhere: once
    `StreamingResponse` has started sending its 200 OK, a mid-stream failure
    (e.g. an OpenRouter call inside a specialist) can no longer become an
    HTTP error status, so it is converted into a terminal `ERROR` event
    instead of silently truncating the connection.
    """

    try:
        for event in events:
            yield f"data: {event.model_dump_json()}\n\n"
    except Exception as exc:
        error_event = TurnStreamEvent(type=TurnStreamEventType.ERROR, detail=str(exc))
        yield f"data: {error_event.model_dump_json()}\n\n"


app = create_app()
