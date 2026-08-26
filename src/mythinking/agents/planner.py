"""Planner specialist for proposing structured next-action candidates."""

from typing import Any

from pydantic import BaseModel

from mythinking.prompts import PromptRegistry
from mythinking.state import PlannerAnalysis, ProjectState


class Planner:
    """Call the next-action prompt and enforce a typed response contract."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "planner",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def analyze(self, project_state: ProjectState, user_message: str) -> PlannerAnalysis:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "project_state": project_state.model_dump_json(indent=2),
                "user_message": user_message,
            }
        )
        structured_model = self.model.with_structured_output(PlannerAnalysis)
        response = structured_model.invoke(rendered)
        return _validate_model_output(response, PlannerAnalysis)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
