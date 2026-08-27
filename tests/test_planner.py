from pathlib import Path

from mythinking.agents.planner import Planner
from mythinking.prompts import PromptRegistry
from mythinking.state import NextAction, NorthStar, ProjectState

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


class FakeStructuredModel:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.rendered_prompt = ""

    def invoke(self, rendered_prompt: str) -> dict:
        self.rendered_prompt = rendered_prompt
        return self.payload


class FakeModel:
    def __init__(self, payload: dict) -> None:
        self.structured_model = FakeStructuredModel(payload)

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        return self.structured_model


def test_planner_renders_scoped_context_not_raw_state_dump() -> None:
    model = FakeModel({})
    agent = Planner(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(
        north_star=NorthStar(title="Focus app"),
        open_questions=["What's the MVP?"],
        next_actions=[NextAction(description="Talk to 5 users")],
    )

    agent.analyze(project_state, "What should I actually do next?")

    rendered = model.structured_model.rendered_prompt
    assert "Focus app" in rendered
    assert "What's the MVP?" in rendered
    assert "Talk to 5 users" in rendered
    assert '"schema_version"' not in rendered
