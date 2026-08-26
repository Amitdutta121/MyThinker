from pathlib import Path

from mythinking.agents.supervisor import SupervisorAgent
from mythinking.prompts import PromptRegistry
from mythinking.state import (
    BranchCommand,
    BranchCommandAction,
    BranchStatus,
    ConvergenceOption,
    DriftAssessment,
    DriftStatus,
    EvidenceItem,
    EvidenceKind,
    IdeaBranch,
    NextAction,
    NextActionDraft,
    PlannerAnalysis,
    ProjectState,
    ResearcherAnalysis,
    ResearchTask,
    ResearchTaskStatus,
    SynthesizerAnalysis,
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


def test_supervisor_renders_the_evidence_ledger_into_the_prompt() -> None:
    model = FakeModel({"message": "Noted.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    project_state.evidence = [
        EvidenceItem(
            claim="Remote work always reduces innovation",
            kind=EvidenceKind.HYPOTHESIS,
        )
    ]

    agent.respond(project_state, "What should we test next?")

    rendered = model.structured_model.rendered_prompt.lower()
    assert "hypotheses (unverified)" in rendered
    assert "remote work always reduces innovation" in rendered


def test_supervisor_renders_branch_alternatives_into_the_prompt() -> None:
    model = FakeModel({"message": "Here are the options.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.EXPLORE)
    project_state.branches = [
        IdeaBranch(
            name="Newsletter Idea",
            summary="Start a newsletter for solo founders",
            status=BranchStatus.ACTIVE,
        )
    ]

    agent.respond(project_state, "Give me some alternatives.")

    rendered = model.structured_model.rendered_prompt.lower()
    assert "newsletter idea" in rendered
    assert "start a newsletter for solo founders" in rendered


def test_supervisor_adds_default_converge_question_when_model_omits_one() -> None:
    model = FakeModel({"message": "Here is the tradeoff comparison.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CONVERGE)
    synthesis = SynthesizerAnalysis(
        options_considered=[ConvergenceOption(branch_name="Newsletter Idea")],
        recommended_choice="Start with the newsletter",
    )

    reply = agent.respond(
        project_state,
        "Help me decide between these options.",
        synthesis=synthesis,
    )

    assert reply.question == (
        "Does this recommended choice work, or should we keep comparing options?"
    )
    assert reply.question in reply.message


def test_supervisor_renders_open_research_tasks_into_the_prompt() -> None:
    model = FakeModel({"message": "Noted.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    project_state.research_tasks = [
        ResearchTask(question="Do we ship weekly?", status=ResearchTaskStatus.OPEN)
    ]

    agent.respond(project_state, "What should we focus on next?")

    rendered = model.structured_model.rendered_prompt.lower()
    assert "do we ship weekly?" in rendered


def test_supervisor_adds_default_research_question_when_model_omits_one() -> None:
    model = FakeModel({"message": "Here is what I found.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.RESEARCH)
    research_analysis = ResearcherAnalysis(
        answer="We ship every Friday according to the changelog.",
        task_resolved=True,
    )

    reply = agent.respond(
        project_state,
        "Can you research whether we ship weekly?",
        research_analysis=research_analysis,
    )

    assert reply.question == "Does this research answer hold up, or should we keep digging?"
    assert reply.question in reply.message


def test_supervisor_renders_the_next_actions_plan_into_the_prompt() -> None:
    model = FakeModel({"message": "Noted.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    project_state.next_actions = [
        NextAction(description="Draft the first newsletter issue", time_box_minutes=30)
    ]

    agent.respond(project_state, "What have we already planned?")

    rendered = model.structured_model.rendered_prompt.lower()
    assert "draft the first newsletter issue" in rendered


def test_supervisor_adds_default_decide_question_when_model_omits_one() -> None:
    model = FakeModel({"message": "Here is a next step.", "question": ""})
    agent = SupervisorAgent(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(current_mode=ThinkingMode.DECIDE)
    planner_analysis = PlannerAnalysis(
        next_actions_to_add=[
            NextActionDraft(description="Draft the first newsletter issue", time_box_minutes=30)
        ]
    )

    reply = agent.respond(
        project_state,
        "What should I do next?",
        planner_analysis=planner_analysis,
    )

    assert reply.question == "Does this next action work, or should we plan something else?"
    assert reply.question in reply.message
