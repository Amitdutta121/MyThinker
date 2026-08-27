from pathlib import Path
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from mythinking.agents.supervisor import SupervisorAgent
from mythinking.context import ContextRetriever
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
    NextActionDraft,
    PlannerAnalysis,
    ProjectState,
    ResearcherAnalysis,
    SynthesizerAnalysis,
    TangentDisposition,
    ThinkingMode,
)

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


class FakeToolCallingModel(FakeMessagesListChatModel):
    """A scripted chat model create_agent can drive: cycles through `responses`,
    and accepts `bind_tools` as a no-op so it can be handed to `create_agent`."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeToolCallingModel":
        return self


class _FakeStore:
    """Below-threshold ContextRetriever never calls .search(), so this never
    needs to behave like a real SqliteStore for these tests."""

    def search(
        self,
        namespace: Any,
        *,
        query: Any = None,
        filter: Any = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list:
        raise AssertionError("should not query the store below the configured threshold")


def _reply_response(message: str, question: str = "", call_id: str = "reply") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "SupervisorReply",
                "args": {"message": message, "question": question},
                "id": call_id,
            }
        ],
    )


def _agent(model: FakeToolCallingModel) -> SupervisorAgent:
    context_retriever = ContextRetriever(_FakeStore(), threshold=1000, top_k=3)
    return SupervisorAgent(PromptRegistry(PROMPT_DIR), model, context_retriever)


def test_supervisor_adds_default_drift_question_when_model_omits_one() -> None:
    model = FakeToolCallingModel(responses=[_reply_response("That looks like a side topic.")])
    agent = _agent(model)
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


def test_supervisor_adds_branch_switch_confirmation_when_model_omits_one() -> None:
    model = FakeToolCallingModel(responses=[_reply_response("Good move.")])
    agent = _agent(model)
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


def test_supervisor_adds_return_to_main_confirmation_when_model_omits_one() -> None:
    model = FakeToolCallingModel(responses=[_reply_response("Refocusing.")])
    agent = _agent(model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    branch_command = BranchCommand(action=BranchCommandAction.RETURN_TO_MAIN)

    reply = agent.respond(
        project_state,
        "Let's return to the main goal.",
        branch_command=branch_command,
    )

    assert "Switched the active thread back to the main goal." in reply.message


def test_supervisor_adds_default_converge_question_when_model_omits_one() -> None:
    model = FakeToolCallingModel(responses=[_reply_response("Here is the tradeoff comparison.")])
    agent = _agent(model)
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


def test_supervisor_adds_default_research_question_when_model_omits_one() -> None:
    model = FakeToolCallingModel(responses=[_reply_response("Here is what I found.")])
    agent = _agent(model)
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


def test_supervisor_adds_default_decide_question_when_model_omits_one() -> None:
    model = FakeToolCallingModel(responses=[_reply_response("Here is a next step.")])
    agent = _agent(model)
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


def test_supervisor_can_call_a_context_tool_before_answering() -> None:
    """Proves the tool-calling plumbing: a scripted call to a real,
    project-state-bound tool resolves correctly (an unknown/mismatched tool
    name here would raise), then the loop still reaches the final reply.
    Tool *content* correctness is covered by test_tools.py directly."""

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_evidence_ledger", "args": {"topic": "innovation"}, "id": "1"}
                ],
            ),
            _reply_response("Here's what we've found so far."),
        ]
    )
    agent = _agent(model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    project_state.evidence = [
        EvidenceItem(claim="Remote work always reduces innovation", kind=EvidenceKind.HYPOTHESIS)
    ]

    reply = agent.respond(project_state, "What should we test next?")

    assert reply.message == "Here's what we've found so far."


def test_supervisor_falls_back_to_a_message_when_the_loop_ends_without_a_reply() -> None:
    """ModelCallLimitMiddleware can end the loop before a SupervisorReply
    tool call is ever made -- the fallback message must still satisfy
    SupervisorReply's min_length=1 contract rather than crash."""

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "get_branch_alternatives", "args": {}, "id": str(i)}],
            )
            for i in range(10)
        ]
    )
    agent = _agent(model)
    project_state = ProjectState(current_mode=ThinkingMode.CAPTURE)
    project_state.branches = [IdeaBranch(name="Newsletter Idea", status=BranchStatus.ACTIVE)]

    reply = agent.respond(project_state, "Keep looking things up forever.")

    assert reply.message
