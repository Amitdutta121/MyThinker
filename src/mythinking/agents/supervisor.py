"""Supervisor agent that owns the user-facing response."""

from typing import Any

from pydantic import BaseModel, Field

from mythinking.prompts import PromptRegistry
from mythinking.state import AssistantTurn, FrameAnalysis, ProjectState, ThinkingMode


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
    ) -> AssistantTurn:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "project_state": project_state.model_dump_json(indent=2),
                "user_message": user_message,
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
