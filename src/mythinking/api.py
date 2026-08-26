"""HTTP API over `ThinkingRuntime` (M7a: non-streaming turns and state reads).

This module is a thin adapter: every request maps directly onto an existing
`ThinkingRuntime`/`StateRepository` method. It holds no business logic of its
own, so the graph and specialists stay testable without the API running.
"""

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from mythinking.runtime import ThinkingRuntime, create_runtime
from mythinking.state import AssistantTurn, ProjectState, ThinkingMode


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

    return app


app = create_app()
