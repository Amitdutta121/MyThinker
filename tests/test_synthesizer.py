from pathlib import Path

from mythinking.agents.synthesizer import Synthesizer
from mythinking.prompts import PromptRegistry
from mythinking.state import BranchStatus, IdeaBranch, NorthStar, ProjectState

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


def test_synthesizer_renders_scoped_context_including_all_branch_names() -> None:
    model = FakeModel({})
    agent = Synthesizer(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(
        north_star=NorthStar(title="Focus app"),
        branches=[
            IdeaBranch(name="Newsletter", status=BranchStatus.ACTIVE),
            IdeaBranch(name="Old Idea", status=BranchStatus.DISCARDED),
        ],
    )

    agent.analyze(project_state, "Help me pick one of these")

    rendered = model.structured_model.rendered_prompt
    assert "Focus app" in rendered
    assert "Newsletter" in rendered
    assert "Old Idea" in rendered
    assert '"schema_version"' not in rendered
