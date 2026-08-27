"""HTTP API over `ThinkingRuntime` (M7a: non-streaming turns and state reads;
M7b: SSE streaming of turns).

This module is a thin adapter: every request maps directly onto an existing
`ThinkingRuntime`/`StateRepository` method. It holds no business logic of its
own, so the agent and its tools stay testable without the API running.
"""

from collections.abc import Iterator
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mythinking.documents import Document
from mythinking.retrieval import list_documents
from mythinking.runtime import ThinkingRuntime, create_runtime
from mythinking.state import (
    AssistantTurn,
    ProjectState,
    ThinkingMode,
    TurnStreamEvent,
    TurnStreamEventType,
)


class TurnRequest(BaseModel):
    message: str = Field(min_length=1)
    project_id: str | None = None


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

    @app.get("/projects/{project_id}/documents", response_model=list[Document])
    def list_project_documents(
        project_id: str,
        runtime: ThinkingRuntime = Depends(get_runtime),
    ) -> list[Document]:
        if runtime.store is None:
            return []
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
