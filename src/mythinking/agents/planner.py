"""Planner specialist for proposing structured next-action candidates."""

from typing import Any

from pydantic import BaseModel

from mythinking.context import format_north_star_brief, format_open_questions
from mythinking.exploration import format_branch_alternatives
from mythinking.planning import format_next_actions
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
                "north_star_brief": format_north_star_brief(project_state),
                "open_questions": format_open_questions(project_state),
                "branch_alternatives": format_branch_alternatives(project_state),
                "next_actions_plan": format_next_actions(project_state),
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
