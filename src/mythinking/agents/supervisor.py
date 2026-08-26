"""Supervisor agent that owns the user-facing response."""

from typing import Any

from pydantic import BaseModel, Field

from mythinking.prompts import PromptRegistry
from mythinking.state import (
    AssistantTurn,
    DriftAssessment,
    DriftStatus,
    FrameAnalysis,
    ProjectState,
    TangentDisposition,
    ThinkingMode,
)


class SupervisorReply(BaseModel):
    """LLM-owned fields for a single user-facing turn."""

    message: str = Field(min_length=1)
    question: str = ""


class SupervisorAgent:
    """Generate the only user-facing assistant response for the turn."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "lead_partner",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def respond(
        self,
        project_state: ProjectState,
        user_message: str,
        frame_analysis: FrameAnalysis | None = None,
        drift_assessment: DriftAssessment | None = None,
    ) -> AssistantTurn:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "project_state": project_state.model_dump_json(indent=2),
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
            }
        )
        structured_model = self.model.with_structured_output(SupervisorReply)
        reply = _validate_model_output(structured_model.invoke(rendered), SupervisorReply)
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
        message = reply.message.strip()
        if question and question not in message:
            message = f"{message}\n\n{question}"
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
