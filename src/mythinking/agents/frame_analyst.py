"""Frame Analyst specialist for extracting faithful project-state updates."""

from typing import Any

from pydantic import BaseModel

from mythinking.prompts import PromptRegistry
from mythinking.state import FrameAnalysis, ProjectState


class FrameAnalyst:
    """Call the frame-analysis prompt and enforce a typed response contract."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "frame_analyst",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def analyze(self, project_state: ProjectState, user_message: str) -> FrameAnalysis:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "project_state": project_state.model_dump_json(indent=2),
                "user_message": user_message,
            }
        )
        structured_model = self.model.with_structured_output(FrameAnalysis)
        response = structured_model.invoke(rendered)
        return _validate_model_output(response, FrameAnalysis)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
