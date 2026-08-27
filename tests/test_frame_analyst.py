from pathlib import Path

from mythinking.agents.frame_analyst import FrameAnalyst
from mythinking.prompts import PromptRegistry
from mythinking.state import Assumption, NorthStar, ProjectState

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


def test_frame_analyst_renders_scoped_context_not_raw_state_dump() -> None:
    model = FakeModel({})
    agent = FrameAnalyst(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(
        north_star=NorthStar(title="Focus app"),
        assumptions=[Assumption(statement="Users want fewer tabs")],
        open_questions=["Who pays for this?"],
    )

    agent.analyze(project_state, "I think we should add a pricing tier")

    rendered = model.structured_model.rendered_prompt
    assert "Focus app" in rendered
    assert "Users want fewer tabs" in rendered
    assert "Who pays for this?" in rendered
    assert '"schema_version"' not in rendered  # no raw ProjectState JSON dump
