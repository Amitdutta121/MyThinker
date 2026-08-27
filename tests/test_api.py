from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

from mythinking.api import create_app
from mythinking.documents import Document
from mythinking.retrieval import index_document, open_document_store
from mythinking.state import (
    AssistantTurn,
    NorthStar,
    ProjectState,
    ThinkingMode,
    TurnStreamEvent,
    TurnStreamEventType,
)


class FakeRepository:
    def __init__(self, states: list[ProjectState]) -> None:
        self.states = states

    def list_recent(self, limit: int = 20) -> list[ProjectState]:
        return self.states[:limit]


class FakeRuntime:
    """Duck-typed stand-in exposing exactly the surface `api.py` depends on."""

    def __init__(
        self,
        *,
        turn: AssistantTurn | None = None,
        project_states: dict[str, ProjectState] | None = None,
        recent_states: list[ProjectState] | None = None,
        error: Exception | None = None,
        stream_events: Iterator[TurnStreamEvent] | list[TurnStreamEvent] | None = None,
        stream_error: Exception | None = None,
        store: Any | None = None,
    ) -> None:
        self.turn = turn
        self.project_states = project_states or {}
        self.error = error
        self.repository = FakeRepository(recent_states or [])
        self.calls: list[tuple[str, str | None]] = []
        self.stream_events = stream_events
        self.stream_error = stream_error
        self.stream_calls: list[tuple[str, str | None]] = []
        self.store = store

    def run_turn(self, message: str, project_id: str | None = None) -> AssistantTurn:
        self.calls.append((message, project_id))
        if self.error is not None:
            raise self.error
        assert self.turn is not None
        return self.turn

    def stream_turn(self, message: str, project_id: str | None = None) -> Iterator[TurnStreamEvent]:
        self.stream_calls.append((message, project_id))
        if self.stream_error is not None:
            raise self.stream_error
        return iter(self.stream_events or [])

    def get_project_state(self, project_id: str) -> ProjectState | None:
        return self.project_states.get(project_id)


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_turn_returns_assistant_turn() -> None:
    turn = AssistantTurn(
        project_id="proj-1",
        mode=ThinkingMode.CAPTURE,
        message="Let's capture the idea.",
        question="What outcome matters most?",
    )
    runtime = FakeRuntime(turn=turn)
    client = TestClient(create_app(runtime))

    response = client.post("/turns", json={"message": "Help me think this through"})

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "proj-1"
    assert body["mode"] == "capture"
    assert body["question"] == "What outcome matters most?"
    assert runtime.calls == [("Help me think this through", None)]


def test_create_turn_passes_project_id_through() -> None:
    turn = AssistantTurn(project_id="proj-9", mode=ThinkingMode.CLARIFY, message="ok")
    runtime = FakeRuntime(turn=turn)
    client = TestClient(create_app(runtime))

    response = client.post("/turns", json={"message": "continue", "project_id": "proj-9"})

    assert response.status_code == 200
    assert runtime.calls == [("continue", "proj-9")]


def test_create_turn_rejects_blank_message() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.post("/turns", json={"message": ""})

    assert response.status_code == 422


def test_create_turn_returns_404_for_unknown_project(monkeypatch) -> None:
    runtime = FakeRuntime(error=KeyError("Unknown project_id: missing"))
    client = TestClient(create_app(runtime))

    response = client.post("/turns", json={"message": "resume this", "project_id": "missing"})

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_create_turn_stream_emits_node_and_turn_events() -> None:
    final_turn = AssistantTurn(project_id="proj-1", mode=ThinkingMode.CAPTURE, message="ok")
    events = [
        TurnStreamEvent(type=TurnStreamEventType.NODE, node="set_north_star"),
        TurnStreamEvent(type=TurnStreamEventType.NODE, node="explore_ideas"),
        TurnStreamEvent(type=TurnStreamEventType.TURN, turn=final_turn),
    ]
    runtime = FakeRuntime(stream_events=events)
    client = TestClient(create_app(runtime))

    response = client.post("/turns/stream", json={"message": "Help me think this through"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [frame for frame in response.text.split("\n\n") if frame]
    assert len(frames) == 3
    assert frames[0] == f"data: {events[0].model_dump_json()}"
    last_event = TurnStreamEvent.model_validate_json(frames[-1].removeprefix("data: "))
    assert last_event.type is TurnStreamEventType.TURN
    assert last_event.turn is not None
    assert last_event.turn.message == "ok"
    assert runtime.stream_calls == [("Help me think this through", None)]


def test_create_turn_stream_rejects_blank_message() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.post("/turns/stream", json={"message": ""})

    assert response.status_code == 422


def test_create_turn_stream_returns_404_for_unknown_project() -> None:
    runtime = FakeRuntime(stream_error=KeyError("Unknown project_id: missing"))
    client = TestClient(create_app(runtime))

    response = client.post(
        "/turns/stream", json={"message": "resume this", "project_id": "missing"}
    )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_create_turn_stream_converts_mid_stream_failure_into_an_error_event() -> None:
    def failing_events() -> Iterator[TurnStreamEvent]:
        yield TurnStreamEvent(type=TurnStreamEventType.NODE, node="capture")
        raise RuntimeError("graph blew up")

    runtime = FakeRuntime(stream_events=failing_events())
    client = TestClient(create_app(runtime))

    response = client.post("/turns/stream", json={"message": "go"})

    assert response.status_code == 200
    frames = [frame for frame in response.text.split("\n\n") if frame]
    assert len(frames) == 2
    last_event = TurnStreamEvent.model_validate_json(frames[-1].removeprefix("data: "))
    assert last_event.type is TurnStreamEventType.ERROR
    assert "graph blew up" in last_event.detail


def test_list_projects_returns_summaries_newest_first() -> None:
    older = ProjectState(north_star=NorthStar(title="Older idea"))
    newer = ProjectState(north_star=NorthStar(title="Newer idea"))
    runtime = FakeRuntime(recent_states=[newer, older])
    client = TestClient(create_app(runtime))

    response = client.get("/projects")

    assert response.status_code == 200
    titles = [row["title"] for row in response.json()]
    assert titles == ["Newer idea", "Older idea"]


def test_list_projects_honors_limit_query_param() -> None:
    states = [ProjectState(north_star=NorthStar(title=f"Idea {i}")) for i in range(5)]
    runtime = FakeRuntime(recent_states=states)
    client = TestClient(create_app(runtime))

    response = client.get("/projects", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_project_returns_full_state() -> None:
    state = ProjectState(north_star=NorthStar(title="Full state idea"))
    runtime = FakeRuntime(project_states={state.project_id: state})
    client = TestClient(create_app(runtime))

    response = client.get(f"/projects/{state.project_id}")

    assert response.status_code == 200
    assert response.json()["project_id"] == state.project_id
    assert response.json()["north_star"]["title"] == "Full state idea"


def test_get_project_returns_404_for_unknown_project() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/projects/missing")

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


def test_list_project_documents_returns_empty_list_when_no_store() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/projects/proj-1/documents")

    assert response.status_code == 200
    assert response.json() == []


def test_list_project_documents_returns_stored_documents(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        document = Document(
            project_id="proj-1", title="A source", source_url="https://x", content="body"
        )
        index_document(store, "proj-1", document)
        runtime = FakeRuntime(store=store)
        client = TestClient(create_app(runtime))

        response = client.get("/projects/proj-1/documents")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["title"] == "A source"


def test_cors_allows_the_frontend_dev_origin() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_allows_the_frontend_dev_fallback_port() -> None:
    """Next.js falls back to :3001 when :3000 is already taken locally."""
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/health", headers={"Origin": "http://localhost:3001"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_create_app_defaults_to_lazy_runtime_construction(monkeypatch) -> None:
    """Building the app (and hitting read-only routes) must not require an API key."""

    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert app.state.runtime is None
