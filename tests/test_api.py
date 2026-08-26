from fastapi.testclient import TestClient

from mythinking.api import create_app
from mythinking.state import AssistantTurn, NorthStar, ProjectState, ThinkingMode


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
    ) -> None:
        self.turn = turn
        self.project_states = project_states or {}
        self.error = error
        self.repository = FakeRepository(recent_states or [])
        self.calls: list[tuple[str, str | None]] = []

    def run_turn(self, message: str, project_id: str | None = None) -> AssistantTurn:
        self.calls.append((message, project_id))
        if self.error is not None:
            raise self.error
        assert self.turn is not None
        return self.turn

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


def test_create_app_defaults_to_lazy_runtime_construction(monkeypatch) -> None:
    """Building the app (and hitting read-only routes) must not require an API key."""

    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert app.state.runtime is None
