from pathlib import Path

from mythinking.agents.supervisor import SupervisorAgent
from mythinking.prompts import PromptRegistry
from mythinking.state import (
    BranchCommand,
    BranchCommandAction,
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


def test_supervisor_adds_branch_switch_confirmation_when_model_omits_one() -> None:
    model = FakeModel({"message": "Good move.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    branch_command = BranchCommand(
        action=BranchCommandAction.SWITCH,
        target_branch_id="branch-1",
        target_branch_name="Newsletter Idea",
        matched_text="Switch to the newsletter branch.",
    )

    reply = agent.respond(
        project_state,
        "Switch to the newsletter branch.",
        branch_command=branch_command,
    )

    assert 'Switched the active thread to "Newsletter Idea".' in reply.message
    assert "newsletter idea" in model.structured_model.rendered_prompt.lower()


def test_supervisor_adds_return_to_main_confirmation_when_model_omits_one() -> None:
    model = FakeModel({"message": "Refocusing.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    branch_command = BranchCommand(action=BranchCommandAction.RETURN_TO_MAIN)

    reply = agent.respond(
        project_state,
        "Let's return to the main goal.",
        branch_command=branch_command,
    )

    assert "Switched the active thread back to the main goal." in reply.message
