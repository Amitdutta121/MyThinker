"""Synthesizer specialist for converging alternatives into a decision-ready summary."""

from typing import Any

from pydantic import BaseModel

from mythinking.context import format_north_star_brief
from mythinking.exploration import format_all_branch_names, format_branch_alternatives
from mythinking.prompts import PromptRegistry
from mythinking.state import ProjectState, SynthesizerAnalysis


class Synthesizer:
    """Call the convergence prompt and enforce a typed response contract."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "synthesizer",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def analyze(self, project_state: ProjectState, user_message: str) -> SynthesizerAnalysis:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "north_star_brief": format_north_star_brief(project_state),
                "all_branch_names": format_all_branch_names(project_state),
                "branch_alternatives": format_branch_alternatives(project_state),
                "user_message": user_message,
            }
        )
        structured_model = self.model.with_structured_output(SynthesizerAnalysis)
        response = structured_model.invoke(rendered)
        return _validate_model_output(response, SynthesizerAnalysis)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
