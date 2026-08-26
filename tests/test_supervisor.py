from pathlib import Path

from mythinking.agents.supervisor import SupervisorAgent
from mythinking.prompts import PromptRegistry
from mythinking.state import (
    DriftAssessment,
    DriftStatus,
    ProjectState,
    TangentDisposition,
    ThinkingMode,
)

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


class FakeStructuredModel:
    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload
        self.rendered_prompt = ""

    def invoke(self, rendered_prompt: str) -> dict[str, str]:
        self.rendered_prompt = rendered_prompt
        return self.payload


class FakeModel:
    def __init__(self, payload: dict[str, str]) -> None:
        self.structured_model = FakeStructuredModel(payload)

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        return self.structured_model


def test_supervisor_adds_default_drift_question_when_model_omits_one() -> None:
    model = FakeModel({"message": "That looks like a side topic.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CHALLENGE)
    drift_assessment = DriftAssessment(
        status=DriftStatus.DRIFTED,
        disposition=TangentDisposition.BRANCH,
        tangent_summary="Tell me everything about vector databases",
    )

    reply = agent.respond(
        project_state,
        "Tell me everything about vector databases.",
        drift_assessment=drift_assessment,
    )

    assert reply.question == (
        "Should we return to the main goal, or spin this tangent into its own branch?"
    )
    assert reply.question in reply.message
    assert "vector databases" in model.structured_model.rendered_prompt.lower()
