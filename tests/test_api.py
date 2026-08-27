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
    ChatMessage,
    ChatRole,
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
        histories: dict[str, list[ChatMessage]] | None = None,
        edit_result: ProjectState | None = None,
        edit_error: Exception | None = None,
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
        self.histories = histories or {}
        self.edit_result = edit_result
        self.edit_error = edit_error
        self.edit_calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _edit(self, name: str, *args: Any, **kwargs: Any) -> ProjectState:
        self.edit_calls.append((name, args, kwargs))
        if self.edit_error is not None:
            raise self.edit_error
        assert self.edit_result is not None
        return self.edit_result

    def edit_north_star(self, project_id: str, *, title: str | None = None) -> ProjectState:
        return self._edit("edit_north_star", project_id, title=title)

    def add_decision(self, project_id: str, **kwargs: Any) -> ProjectState:
        return self._edit("add_decision", project_id, **kwargs)

    def edit_decision(self, project_id: str, decision_id: str, **kwargs: Any) -> ProjectState:
        return self._edit("edit_decision", project_id, decision_id, **kwargs)

    def delete_decision(self, project_id: str, decision_id: str) -> ProjectState:
        return self._edit("delete_decision", project_id, decision_id)

    def approve_proposal(self, project_id: str) -> ProjectState:
        return self._edit("approve_proposal", project_id)

    def dismiss_proposal(self, project_id: str) -> ProjectState:
        return self._edit("dismiss_proposal", project_id)

    def add_next_action(self, project_id: str, **kwargs: Any) -> ProjectState:
        return self._edit("add_next_action", project_id, **kwargs)

    def edit_next_action(self, project_id: str, action_id: str, **kwargs: Any) -> ProjectState:
        return self._edit("edit_next_action", project_id, action_id, **kwargs)

    def delete_next_action(self, project_id: str, action_id: str) -> ProjectState:
        return self._edit("delete_next_action", project_id, action_id)

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

    def get_history(self, project_id: str) -> list[ChatMessage]:
        if project_id not in self.project_states and project_id not in self.histories:
            raise KeyError(f"Unknown project_id: {project_id}")
        return self.histories.get(project_id, [])


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


def _edit_client(state: ProjectState | None = None, error: Exception | None = None):
    result = state or ProjectState(north_star=NorthStar(title="Edited"))
    runtime = FakeRuntime(edit_result=result, edit_error=error)
    return TestClient(create_app(runtime)), runtime


def test_patch_north_star_maps_body_to_runtime_and_returns_state() -> None:
    client, runtime = _edit_client()

    response = client.patch("/projects/p1/north-star", json={"title": "Personal KB"})

    assert response.status_code == 200
    assert response.json()["north_star"]["title"] == "Edited"
    assert runtime.edit_calls == [("edit_north_star", ("p1",), {"title": "Personal KB"})]


def test_patch_north_star_unknown_project_is_404() -> None:
    client, _ = _edit_client(error=KeyError("Unknown project_id: missing"))

    response = client.patch("/projects/missing/north-star", json={"title": "x"})

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_patch_north_star_blank_title_is_400() -> None:
    client, _ = _edit_client(error=ValueError("Goal cannot be empty."))

    response = client.patch("/projects/p1/north-star", json={"title": "   "})

    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_create_decision_requires_a_choice() -> None:
    client, _ = _edit_client()

    response = client.post("/projects/p1/decisions", json={"question": "Sync?"})

    assert response.status_code == 422


def test_create_decision_returns_201_and_passes_fields() -> None:
    client, runtime = _edit_client()

    response = client.post(
        "/projects/p1/decisions",
        json={"question": "Sync?", "choice": "Single-device", "reversible": False},
    )

    assert response.status_code == 201
    name, args, kwargs = runtime.edit_calls[0]
    assert name == "add_decision"
    assert args == ("p1",)
    assert kwargs["choice"] == "Single-device"
    assert kwargs["reversible"] is False


def test_patch_and_delete_decision_route_to_runtime() -> None:
    client, runtime = _edit_client()

    client.patch("/projects/p1/decisions/d9", json={"rationale": "cheaper"})
    client.delete("/projects/p1/decisions/d9")

    assert runtime.edit_calls[0][:2] == ("edit_decision", ("p1", "d9"))
    assert runtime.edit_calls[0][2]["rationale"] == "cheaper"
    assert runtime.edit_calls[1][:2] == ("delete_decision", ("p1", "d9"))


def test_delete_decision_unknown_id_is_404() -> None:
    client, _ = _edit_client(error=KeyError("Unknown decision_id: d9"))

    response = client.delete("/projects/p1/decisions/d9")

    assert response.status_code == 404


def test_approve_proposal_routes_to_runtime() -> None:
    client, runtime = _edit_client()

    response = client.post("/projects/p1/proposal/approve")

    assert response.status_code == 200
    assert runtime.edit_calls == [("approve_proposal", ("p1",), {})]


def test_approve_proposal_without_a_proposal_is_400() -> None:
    client, _ = _edit_client(error=ValueError("There is no pending proposal to approve."))

    response = client.post("/projects/p1/proposal/approve")

    assert response.status_code == 400
    assert "proposal" in response.json()["detail"]


def test_dismiss_proposal_routes_to_runtime() -> None:
    client, runtime = _edit_client()

    response = client.delete("/projects/p1/proposal")

    assert response.status_code == 200
    assert runtime.edit_calls == [("dismiss_proposal", ("p1",), {})]


def test_create_next_action_returns_201_and_passes_fields() -> None:
    client, runtime = _edit_client()

    response = client.post(
        "/projects/p1/next-actions",
        json={"description": "Call three users", "time_box_minutes": 45},
    )

    assert response.status_code == 201
    name, args, kwargs = runtime.edit_calls[0]
    assert name == "add_next_action"
    assert args == ("p1",)
    assert kwargs["description"] == "Call three users"
    assert kwargs["time_box_minutes"] == 45


def test_create_next_action_rejects_zero_time_box() -> None:
    client, _ = _edit_client()

    response = client.post(
        "/projects/p1/next-actions",
        json={"description": "x", "time_box_minutes": 0},
    )

    assert response.status_code == 422


def test_patch_and_delete_next_action_route_to_runtime() -> None:
    client, runtime = _edit_client()

    client.patch("/projects/p1/next-actions/a3", json={"completed": True})
    client.delete("/projects/p1/next-actions/a3")

    assert runtime.edit_calls[0][:2] == ("edit_next_action", ("p1", "a3"))
    assert runtime.edit_calls[0][2]["completed"] is True
    assert runtime.edit_calls[1][:2] == ("delete_next_action", ("p1", "a3"))


def test_get_project_messages_replays_the_transcript() -> None:
    state = ProjectState(north_star=NorthStar(title="Has history"))
    runtime = FakeRuntime(
        project_states={state.project_id: state},
        histories={
            state.project_id: [
                ChatMessage(role=ChatRole.USER, content="Help me think"),
                ChatMessage(role=ChatRole.ASSISTANT, content="What's the goal?"),
            ]
        },
    )
    client = TestClient(create_app(runtime))

    response = client.get(f"/projects/{state.project_id}/messages")

    assert response.status_code == 200
    assert response.json() == [
        {"role": "user", "content": "Help me think"},
        {"role": "assistant", "content": "What's the goal?"},
    ]


def test_get_project_messages_returns_empty_list_for_a_never_run_project() -> None:
    state = ProjectState(north_star=NorthStar(title="No history yet"))
    runtime = FakeRuntime(project_states={state.project_id: state})
    client = TestClient(create_app(runtime))

    response = client.get(f"/projects/{state.project_id}/messages")

    assert response.status_code == 200
    assert response.json() == []


def test_get_project_messages_returns_404_for_unknown_project() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.get("/projects/missing/messages")

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


def test_upload_project_document_ingests_and_lists_it(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        state = ProjectState(north_star=NorthStar(title="Has an upload"))
        runtime = FakeRuntime(project_states={state.project_id: state}, store=store)
        client = TestClient(create_app(runtime))

        response = client.post(
            f"/projects/{state.project_id}/documents",
            params={"filename": "notes.md"},
            content=b"# Heading\n\nSome body text worth indexing.",
        )

        assert response.status_code == 201
        assert response.json()["title"] == "notes.md"

        listed = client.get(f"/projects/{state.project_id}/documents")
        assert [d["title"] for d in listed.json()] == ["notes.md"]


def test_upload_project_document_unknown_project_is_404(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        runtime = FakeRuntime(store=store)
        client = TestClient(create_app(runtime))

        response = client.post(
            "/projects/missing/documents", params={"filename": "a.txt"}, content=b"hello"
        )

        assert response.status_code == 404


def test_upload_project_document_rejects_bad_file_with_422(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        state = ProjectState(north_star=NorthStar(title="Bad upload"))
        runtime = FakeRuntime(project_states={state.project_id: state}, store=store)
        client = TestClient(create_app(runtime))

        response = client.post(
            f"/projects/{state.project_id}/documents",
            params={"filename": "malware.exe"},
            content=b"MZ",
        )

        assert response.status_code == 422
        assert "Unsupported file type" in response.json()["detail"]


def test_upload_project_document_without_store_is_503() -> None:
    state = ProjectState(north_star=NorthStar(title="No store configured"))
    runtime = FakeRuntime(project_states={state.project_id: state})
    client = TestClient(create_app(runtime))

    response = client.post(
        f"/projects/{state.project_id}/documents",
        params={"filename": "a.txt"},
        content=b"hello",
    )

    assert response.status_code == 503


def test_delete_project_document_removes_it_and_returns_remaining(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        keep = Document(project_id="proj-1", title="Keep", content="keep")
        drop = Document(project_id="proj-1", title="Drop", content="drop")
        for doc in (keep, drop):
            index_document(store, "proj-1", doc)
        client = TestClient(create_app(FakeRuntime(store=store)))

        response = client.delete(f"/projects/proj-1/documents/{drop.id}")

        assert response.status_code == 200
        assert [d["title"] for d in response.json()] == ["Keep"]
        listed = client.get("/projects/proj-1/documents")
        assert [d["id"] for d in listed.json()] == [keep.id]


def test_delete_project_document_unknown_id_is_404(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        client = TestClient(create_app(FakeRuntime(store=store)))

        response = client.delete("/projects/proj-1/documents/missing")

        assert response.status_code == 404


def test_delete_project_document_without_store_is_503() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.delete("/projects/proj-1/documents/whatever")

    assert response.status_code == 503


def test_delete_project_documents_bulk_removes_selected(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        keep = Document(project_id="proj-1", title="Keep")
        drop_a = Document(project_id="proj-1", title="Drop A")
        drop_b = Document(project_id="proj-1", title="Drop B")
        for doc in (keep, drop_a, drop_b):
            index_document(store, "proj-1", doc)
        client = TestClient(create_app(FakeRuntime(store=store)))

        response = client.post(
            "/projects/proj-1/documents/delete",
            json={"ids": [drop_a.id, "ghost", drop_b.id]},
        )

        assert response.status_code == 200
        assert [d["title"] for d in response.json()] == ["Keep"]


def test_delete_project_documents_bulk_requires_ids(tmp_path: Path) -> None:
    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=1) as store:
        client = TestClient(create_app(FakeRuntime(store=store)))

        response = client.post("/projects/proj-1/documents/delete", json={"ids": []})

        assert response.status_code == 422


def test_delete_project_documents_bulk_without_store_is_503() -> None:
    client = TestClient(create_app(FakeRuntime()))

    response = client.post("/projects/proj-1/documents/delete", json={"ids": ["a"]})

    assert response.status_code == 503


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
