from pathlib import Path

from mythinking.agents.evidence_analyst import EvidenceAnalyst
from mythinking.prompts import PromptRegistry
from mythinking.state import EvidenceItem, EvidenceKind, ProjectState, ResearchTask

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


class FakeStructuredModel:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.rendered_prompt = ""

    def invoke(self, rendered_prompt: str) -> dict:
        self.rendered_prompt = rendered_prompt
        return self.payload


class FakeModel:
    def __init__(self, payload: dict) -> None:
        self.structured_model = FakeStructuredModel(payload)

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        return self.structured_model


def test_evidence_analyst_renders_scoped_context_not_raw_state_dump() -> None:
    model = FakeModel({})
    agent = EvidenceAnalyst(PromptRegistry(PROMPT_DIR), model)
    project_state = ProjectState(
        evidence=[
            EvidenceItem(claim="Users churn early", kind=EvidenceKind.FACT, source_url="https://x")
        ],
        research_tasks=[ResearchTask(question="Is there real demand?")],
    )

    agent.analyze(project_state, "Users seem to drop off after signup")

    rendered = model.structured_model.rendered_prompt
    assert "Users churn early" in rendered
    assert "Is there real demand?" in rendered
    assert '"schema_version"' not in rendered  # no raw ProjectState JSON dump
