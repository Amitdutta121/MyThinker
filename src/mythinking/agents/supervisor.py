"""Supervisor agent that owns the user-facing response."""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from pydantic import BaseModel, Field

from mythinking.context import ContextRetriever, format_project_context
from mythinking.prompts import PromptRegistry
from mythinking.state import (
    AssistantTurn,
    BranchCommand,
    BranchCommandAction,
    DriftAssessment,
    DriftStatus,
    ExplorerAnalysis,
    FrameAnalysis,
    PlannerAnalysis,
    ProjectState,
    ResearcherAnalysis,
    SynthesizerAnalysis,
    TangentDisposition,
    ThinkingMode,
)
from mythinking.tools import build_context_tools

_MODEL_CALL_LIMIT = 4
_FALLBACK_MESSAGE = (
    "I need a bit more time to think this through -- could you ask again, "
    "maybe narrowed down a little?"
)


class SupervisorReply(BaseModel):
    """LLM-owned fields for a single user-facing turn."""

    message: str = Field(min_length=1)
    question: str = ""


class SupervisorAgent:
    """Generate the only user-facing assistant response for the turn.

    An agentic `create_agent` loop: the model can call read-only tools over
    this project's own saved evidence/research-tasks/branches/next-actions
    (`tools.build_context_tools`) when it judges a turn's question actually
    needs them, rather than always being handed a fixed context bundle. No
    internet-access tools are bound here -- those stay reachable only
    through the Researcher's own explicit, separately-routed path.
    """

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        context_retriever: ContextRetriever,
        *,
        prompt_id: str = "lead_partner",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.context_retriever = context_retriever
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def respond(
        self,
        project_state: ProjectState,
        user_message: str,
        frame_analysis: FrameAnalysis | None = None,
        drift_assessment: DriftAssessment | None = None,
        branch_command: BranchCommand | None = None,
        exploration_analysis: ExplorerAnalysis | None = None,
        synthesis: SynthesizerAnalysis | None = None,
        research_analysis: ResearcherAnalysis | None = None,
        planner_analysis: PlannerAnalysis | None = None,
    ) -> AssistantTurn:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "project_context": format_project_context(project_state),
                "user_message": user_message,
                "frame_analysis": (
                    frame_analysis.model_dump_json(indent=2)
                    if frame_analysis is not None
                    else "null"
                ),
                "drift_assessment": (
                    drift_assessment.model_dump_json(indent=2)
                    if drift_assessment is not None
                    else "null"
                ),
                "branch_command": (
                    branch_command.model_dump_json(indent=2)
                    if branch_command is not None
                    else "null"
                ),
                "exploration_analysis": (
                    exploration_analysis.model_dump_json(indent=2)
                    if exploration_analysis is not None
                    else "null"
                ),
                "synthesis": (
                    synthesis.model_dump_json(indent=2) if synthesis is not None else "null"
                ),
                "research_analysis": (
                    research_analysis.model_dump_json(indent=2)
                    if research_analysis is not None
                    else "null"
                ),
                "planner_analysis": (
                    planner_analysis.model_dump_json(indent=2)
                    if planner_analysis is not None
                    else "null"
                ),
            }
        )

        agent = create_agent(
            self.model,
            tools=build_context_tools(project_state, self.context_retriever),
            system_prompt=rendered,
            response_format=SupervisorReply,
            middleware=[ModelCallLimitMiddleware(run_limit=_MODEL_CALL_LIMIT, exit_behavior="end")],
        )
        result = agent.invoke({"messages": [("user", user_message)]})
        structured = result.get("structured_response")
        if structured is None:
            reply = SupervisorReply(message=_FALLBACK_MESSAGE)
        else:
            reply = _validate_model_output(structured, SupervisorReply)

        question = reply.question.strip()
        if (
            project_state.current_mode is ThinkingMode.CLARIFY
            and not question
            and frame_analysis is not None
            and frame_analysis.recommended_question.strip()
        ):
            question = frame_analysis.recommended_question.strip()
        if (
            project_state.current_mode is ThinkingMode.CHALLENGE
            and not question
            and drift_assessment is not None
            and drift_assessment.status is DriftStatus.DRIFTED
        ):
            question = _challenge_question(drift_assessment)
        if (
            project_state.current_mode is ThinkingMode.CONVERGE
            and not question
            and synthesis is not None
            and synthesis.recommended_choice.strip()
        ):
            question = "Does this recommended choice work, or should we keep comparing options?"
        if (
            project_state.current_mode is ThinkingMode.RESEARCH
            and not question
            and research_analysis is not None
            and research_analysis.answer.strip()
        ):
            question = "Does this research answer hold up, or should we keep digging?"
        if (
            project_state.current_mode is ThinkingMode.DECIDE
            and not question
            and planner_analysis is not None
            and planner_analysis.next_actions_to_add
        ):
            question = "Does this next action work, or should we plan something else?"
        message = reply.message.strip()
        if question and question not in message:
            message = f"{message}\n\n{question}"
        if branch_command is not None and branch_command.action is not BranchCommandAction.NONE:
            confirmation = _branch_confirmation(branch_command)
            if confirmation.lower() not in message.lower():
                message = f"{message}\n\n{confirmation}" if message else confirmation
        return AssistantTurn(
            project_id=project_state.project_id,
            mode=project_state.current_mode,
            message=message,
            question=question,
        )


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)


def _challenge_question(drift_assessment: DriftAssessment) -> str:
    if drift_assessment.disposition is TangentDisposition.PARKED:
        return "Should we return to the main goal now, or keep this tangent parked for later?"
    return "Should we return to the main goal, or spin this tangent into its own branch?"


def _branch_confirmation(branch_command: BranchCommand) -> str:
    if branch_command.action is BranchCommandAction.RETURN_TO_MAIN:
        return "Switched the active thread back to the main goal."
    name = branch_command.target_branch_name or "that branch"
    return f'Switched the active thread to "{name}".'
