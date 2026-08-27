"""Evidence Analyst specialist for extracting sourced, typed evidence updates."""

from typing import Any

from pydantic import BaseModel

from mythinking.evidence import format_evidence_ledger
from mythinking.prompts import PromptRegistry
from mythinking.research import format_open_research_tasks
from mythinking.state import EvidenceAnalysis, ProjectState


class EvidenceAnalyst:
    """Call the evidence-extraction prompt and enforce a typed response contract."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "evidence_analyst",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def analyze(self, project_state: ProjectState, user_message: str) -> EvidenceAnalysis:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "evidence_ledger": format_evidence_ledger(project_state),
                "open_research_tasks": format_open_research_tasks(project_state),
                "user_message": user_message,
            }
        )
        structured_model = self.model.with_structured_output(EvidenceAnalysis)
        response = structured_model.invoke(rendered)
        return _validate_model_output(response, EvidenceAnalysis)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
